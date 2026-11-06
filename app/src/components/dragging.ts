import { ref } from "vue";
import { useMediaQuery } from "@vueuse/core";
import type { CharacterField, Position } from "@/domain/assembly";

/** A tray item by uid, equipped gear by its position, a character part, or a whole team slot. */
export type Selection =
  { uid: string } | Position | { character: CharacterField; position: number } | { member: number };

/** Drop zones accept only drags that carry this type, not files or text from elsewhere. */
export const DRAG_TYPE = "application/x-siralim-component";

/** The selection being dragged, as JSON. */
export const dragged = ref<string | null>(null);

export function draggedSelection(): Selection | null {
  return dragged.value ? (JSON.parse(dragged.value) as Selection) : null;
}

/**
 * Native HTML5 drag sources, offered to a fine pointer only; on touch screens items are placed
 * by selecting and then tapping a field, and sent back with the item's Back to tray action.
 */
export function useDragSource() {
  const fine = useMediaQuery("(pointer: fine)");
  return (selection: Selection) => {
    if (!fine.value) return {};
    const key = JSON.stringify(selection);
    return {
      draggable: true,
      class: { "drag-source": dragged.value === key },
      onDragstart: (event: DragEvent) => {
        // Drop zones report a "copy" drop effect, so the drag must allow it.
        event.dataTransfer?.setData(DRAG_TYPE, key);
        dragged.value = key;
      },
      onDragend: () => (dragged.value = null),
    };
  };
}
