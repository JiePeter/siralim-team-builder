import { computed, shallowRef } from "vue";
import { defineStore } from "pinia";
import { useStorage } from "@vueuse/core";
import { catalog, teamRules } from "@/data";
import { toastError } from "@/components/toast";
import {
  cloneInstance,
  copyEquipment,
  installCharacterPart,
  moveEquipment,
  newInstance as instance,
  replaceInstance,
  returnCharacterPart,
  returnEquipment,
  returnOrphans,
  type CharacterField,
  type Position,
} from "@/domain/assembly";
import {
  applySwap,
  excessTrait,
  MAX_TRAIT_COPIES,
  newRepeat,
  REPEATED_TRAIT,
  type TraitSwap,
} from "@/domain/placement";
import { encodeTeam, decodeTeam } from "@/domain/share";
import {
  itemId,
  newTeam,
  teamIndex,
  trayTraits,
  validateTeam,
  TeamError,
  type ArtifactConfig,
  type Character,
  type Equipment,
  type Team,
  type TeamIndex,
} from "@/domain/team";

const TEAM_KEY = "siralim-planner.team-v2";
/** Every saved team with its tray; the open one is kept up to date under TEAM_KEY. */
const TEAMS_KEY = "siralim-planner.teams-v2";

interface Library {
  active: number;
  teams: Team[];
}

/** A plain copy: domain code clones with structuredClone, which rejects reactive proxies. */
const plain = <T>(value: T): T => JSON.parse(JSON.stringify(value));

export const BLANK_ARTIFACT = "artifact:0";

export const useTeamStore = defineStore("team", () => {
  const team = useStorage<Team>(TEAM_KEY, newTeam(), undefined, {
    onError: () => toastError("This browser cannot keep the team; export it to keep a copy"),
  });
  const library = useStorage<Library>(TEAMS_KEY, { active: 0, teams: [] }, undefined, {
    onError: () => toastError("This browser cannot keep the team; export it to keep a copy"),
  });
  if (!library.value.teams[library.value.active]) {
    library.value = { active: 0, teams: [plain(team.value)] };
  }
  const teams = computed(() =>
    library.value.teams.map((saved, i) =>
      i === library.value.active ? team.value.name : saved.name,
    ),
  );
  const activeTeam = computed(() => library.value.active);
  const index = shallowRef<TeamIndex | null>(null);
  let loading: Promise<TeamIndex> | null = null;
  const trayCount = computed(() => team.value.inventory.length);

  /** Catalog and team rules, loaded once; every change is validated against them. */
  function rules(): Promise<TeamIndex> {
    loading ??= Promise.all([catalog(), teamRules()]).then(([data, facts]) => {
      index.value = teamIndex(data, facts);
      team.value = trayTraits(index.value, plain(team.value));
      return index.value;
    });
    loading.catch(() => (loading = null));
    return loading;
  }

  /** Apply an edit to a copy of the team; the team changes only when the result is valid. */
  async function change(update: (draft: Team) => Team | void): Promise<Team> {
    const checked = await rules();
    const previous = plain(team.value);
    const draft = plain(team.value);
    // Edits may carry reactive objects from a dialog; validation clones with structuredClone.
    const next = validateTeam(
      checked,
      trayTraits(checked, returnOrphans(plain(update(draft) ?? draft))),
      previous,
    );
    if (excessTrait(checked, previous, next))
      throw new TeamError(`The team and tray hold at most ${MAX_TRAIT_COPIES} of one Trait`);
    if (newRepeat(checked, previous, next)) throw new TeamError(REPEATED_TRAIT);
    team.value = next;
    return team.value;
  }

  /** Apply a change and return a function that restores the team as it was before it. */
  async function undoable(update: (draft: Team) => Team | void): Promise<() => void> {
    const before = plain(team.value);
    const after = JSON.stringify(await change(update));
    return () => {
      if (JSON.stringify(team.value) !== after) throw new Error("The team has changed since");
      team.value = before;
    };
  }

  async function shareUrl(withTray = false): Promise<string> {
    const value = plain(team.value);
    const shared = withTray ? value : { ...value, inventory: [] };
    return `${location.origin}${location.pathname}#team=${await encodeTeam(shared)}`;
  }

  /** Saved teams with the open one brought up to date. */
  function savedTeams(): Team[] {
    const teams = plain(library.value.teams);
    teams[library.value.active] = plain(team.value);
    return teams;
  }

  /** Make team `i` of `teams` the open one, with its own tray. */
  function show(teams: Team[], i: number) {
    const target = teams[i];
    if (!target) throw new Error("Team not found");
    team.value = plain(target);
    library.value = { active: i, teams };
  }

  function openTeam(i: number) {
    show(savedTeams(), i);
  }

  /** Save the open team and open `next` as a new one. */
  function addTeam(next: Team) {
    const teams = savedTeams();
    teams.push(plain(next));
    show(teams, teams.length - 1);
  }

  function createTeam() {
    const names = new Set(teams.value);
    let n = teams.value.length + 1;
    while (names.has(`Team ${n}`)) n++;
    addTeam({ ...newTeam(), name: `Team ${n}` });
  }

  /** Delete the open team and its tray. */
  function deleteTeam() {
    const teams = plain(library.value.teams);
    const gone = library.value.active;
    teams.splice(gone, 1);
    if (!teams.length) {
      team.value = newTeam();
      library.value = { active: 0, teams: [newTeam()] };
      return;
    }
    show(teams, Math.min(gone, teams.length - 1));
  }

  /** Open a shared team, with the tray it carried, as a new team. */
  async function receive(code: string): Promise<boolean> {
    let incoming: Team;
    try {
      const decoded = await decodeTeam(code);
      const checked = await rules();
      incoming = trayTraits(checked, validateTeam(checked, decoded, decoded));
    } catch (error) {
      toastError(
        error instanceof TeamError
          ? `Shared team not opened: ${error.message}`
          : "Shared team link is damaged",
      );
      return false;
    }
    addTeam(incoming);
    return true;
  }

  /** Put a component in the tray; resolves to the undo. */
  function addToTray(id: string) {
    return undoable((next) => {
      next.inventory.push(instance(id));
    });
  }

  function removeFromTray(uid: string) {
    return undoable((next) => {
      next.inventory = next.inventory.filter((item) => item.uid !== uid);
    });
  }

  /** Set the character base, or append an Anointment; resolves to the undo. */
  async function takeCharacterPart(id: string, field: CharacterField) {
    const { catalog: definitions } = await rules();
    return undoable((next) => {
      const item = instance(id);
      next.inventory.push(item);
      const position = field === "characterAnointment" ? next.character.anointments.length : 0;
      return installCharacterPart(next, item.uid, field, definitions, position);
    });
  }

  /** Put a component in the tray and straight into an empty field. */
  function take(id: string, target: Position) {
    return change((next) => {
      const item = instance(id);
      next.inventory.push(item);
      return replaceInstance(next, item.uid, target.slot, target.field, id);
    });
  }

  function install(uid: string, target: Position, resolvedId: string) {
    return change((next) => replaceInstance(next, uid, target.slot, target.field, resolvedId));
  }

  function move(source: Position, target: Position) {
    return change((next) => moveEquipment(next, source, target));
  }

  function swapTraits(swap: TraitSwap) {
    return change((next) => applySwap(next, swap));
  }

  /** Swap two team slots with everything they hold. */
  function swapSlots(a: number, b: number) {
    return change((next) => {
      [next.slots[a], next.slots[b]] = [next.slots[b]!, next.slots[a]!];
    });
  }

  /** Dismiss a slot's Primary; the rest of the slot follows it to the tray. */
  function clearSlot(slot: number) {
    return change((next) => (next.slots[slot]!.base ? returnEquipment(next, slot, "base") : next));
  }

  /** Send the character base and every Anointment back to the tray. */
  function clearCharacter() {
    return change((draft) => {
      let next = draft;
      while (next.character.anointments.length) {
        const last = next.character.anointments.length - 1;
        next = returnCharacterPart(next, "characterAnointment", last);
      }
      return next.character.specialization ? returnCharacterPart(next, "characterBase") : next;
    });
  }

  /** Empty the team and its tray; the name and notes stay. */
  function clearWorkspace() {
    return change((next) => ({ ...newTeam(), name: next.name, notes: next.notes }));
  }

  function unequip(at: Position) {
    return change((next) => returnEquipment(next, at.slot, at.field, at.index));
  }

  /** Equip a configured copy of gear in another slot; resolves to the undo. */
  function copyTo(at: Position, target: Position) {
    return undoable((draft) => {
      const next = copyEquipment(draft, at.slot, at.field, at.index);
      const item = next.inventory.at(-1)!;
      return replaceInstance(next, item.uid, target.slot, target.field, item.id);
    });
  }

  async function copyPoolItem(uid: string): Promise<string> {
    const next = await change((draft) => {
      const item = draft.inventory.find((i) => i.uid === uid);
      if (!item) throw new Error("Component has moved");
      draft.inventory.push(cloneInstance(item));
    });
    return next.inventory.at(-1)!.uid;
  }

  async function placeCharacterPart(uid: string, field: CharacterField, position = 0) {
    const { catalog: definitions } = await rules();
    return change((next) => installCharacterPart(next, uid, field, definitions, position));
  }

  function removeCharacterPart(field: CharacterField, position = 0) {
    return change((next) => returnCharacterPart(next, field, position));
  }

  function setCharacter(character: Character) {
    return change((next) => {
      next.character = character;
    });
  }

  function setGem(at: Position, properties: string[], variants: Record<string, number>) {
    return change((next) => {
      const gems = next.slots[at.slot]!.spells!;
      const position = at.index ?? 0;
      const previous = gems[position]!;
      gems[position] = {
        ...(typeof previous === "string" ? instance(previous) : previous),
        properties,
        property_variants: variants,
      };
    });
  }

  /**
   * Equip a configured Artifact. `taken` is the tray item used for its trait slot; a trait
   * Material it no longer carries goes back to the tray.
   */
  function setArtifact(
    slot: number,
    item: Equipment,
    configuration: ArtifactConfig,
    taken: string | null = null,
  ) {
    return change((next) => {
      const previous = next.slots[slot]!.artifact;
      const before = itemId(previous);
      if (taken) {
        const index = next.inventory.findIndex((i) => i.uid === taken);
        if (index < 0) throw new Error("Component has moved");
        next.inventory.splice(index, 1);
      }
      if (before && before !== item.id && before !== BLANK_ARTIFACT) {
        next.inventory.push(instance(before));
      }
      next.slots[slot]!.artifact = { ...item, artifact: configuration };
    });
  }

  /** Equip a Relic at a rank, taking it from the pool when it is there; an empty id unequips. */
  function setRelic(slot: number, id: string, rank: number) {
    return change((next) => {
      const original = next.slots[slot]!.relic;
      const previous = typeof original === "string" ? instance(original) : original;
      if (!id) {
        if (previous) next.inventory.push(previous);
        delete next.slots[slot]!.relic;
        return;
      }
      const same = previous?.id === id;
      const pooled = same ? undefined : next.inventory.find((i) => i.id === id);
      if (pooled) next.inventory = next.inventory.filter((i) => i.uid !== pooled.uid);
      if (previous && !same) next.inventory.push(previous);
      next.slots[slot]!.relic = {
        ...(pooled ?? (same ? previous! : instance(id))),
        id,
        rank,
      };
    });
  }

  function rename(name: string) {
    return change((next) => {
      next.name = name;
    });
  }

  function setNotes(notes: string) {
    return change((next) => {
      next.notes = notes;
    });
  }

  function replace(value: unknown) {
    return change(() => value as Team);
  }

  return {
    team,
    teams,
    activeTeam,
    openTeam,
    createTeam,
    deleteTeam,
    index,
    trayCount,
    rules,
    shareUrl,
    receive,
    addToTray,
    removeFromTray,
    takeCharacterPart,
    take,
    install,
    move,
    swapTraits,
    swapSlots,
    clearSlot,
    clearCharacter,
    clearWorkspace,
    unequip,
    copyTo,
    copyPoolItem,
    placeCharacterPart,
    removeCharacterPart,
    setCharacter,
    setGem,
    setArtifact,
    setRelic,
    rename,
    setNotes,
    replace,
  };
});
