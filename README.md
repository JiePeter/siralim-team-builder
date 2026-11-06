# Siralim Ultimate Build 组建工具

静态网站：Python 离线构建知识库并导出 JSON 数据包，浏览器端的 Vue 3 应用（`app/`）完成全部查询、校验与组装，运行时没有服务器。

统一搜索 → 右侧已选组件栏 → 独立组装。支持六只生物的本体／融合、Artifact、法术宝石、Relic，以及角色专精天赋、Anointments 和升华配置。搭配候选保留作用范围和条件，是配队线索，不是完整战斗模拟。

队伍保存在浏览器本地（localStorage）；“Share link”生成携带整支队伍的链接，可在其他设备打开或发给他人。

## 运行

需要 Python 3.11+（仅标准库）与 Node 22.12+。

```bash
python -m kb.importer
```

```bash
python -m kb.export
```

```bash
npm --prefix app ci
```

```bash
npm --prefix app run dev
```

`kb.importer` 由 `data/raw/` 重建 `data/knowledge.sqlite3`；`kb.export` 写出 `app/public/data/` 并检查体积预算（总计 500 MB、单文件 5 MB）。开发服务器在 <http://127.0.0.1:5181>（`DEV_PORT` 可改）。`npm --prefix app run build` 后，`npm --prefix app run preview` 在 <http://127.0.0.1:4181>（`PREVIEW_PORT` 可改）提供构建结果。

## 部署

`.github/workflows/pages.yml` 在推送到 `main` 时依次运行导入、导出、`app` 的 lint／typecheck／单元测试与构建，再部署到 GitHub Pages；仓库需在 Pages 设置中选择 GitHub Actions 作为来源。构建使用 Pages 的项目路径作为 `BASE_PATH`。新部署替换带哈希的脚本文件后，部署前打开的页面会在加载失败时自动刷新一次。

## 验证

Python 格式化工具：`python -m venv .venv` 后 `.venv/Scripts/python.exe -m pip install -r requirements-dev.txt`。

```bash
python -m unittest discover -s tests
```

```bash
.venv/Scripts/python.exe -m ruff format --check kb tests
```

```bash
npm --prefix app run lint
```

```bash
npm --prefix app run typecheck
```

```bash
npm --prefix app run test
```

```bash
npm --prefix app run e2e
```

`e2e` 使用现有构建结果，需先运行 `npm --prefix app run build`。`app/tests/golden/` 是已退役 Python 实现记录下的冻结契约数据，不再重新生成。

## 数据与来源

当前正式资料：SiralimJSON 2.0.38（release 0.3.0）。原始社区 XLSX 在 `data/raw/community/2026-10-27/`；参考工具与结构化资料快照在 `data/raw/references/2026-10-27/`，附来源 URL 和上游许可。游戏图片在 `app/public/assets/siralim/`，字体在 `app/src/assets/fonts/`。

游戏名称、效果文本与图片归 Thylacine Studios。第三方致谢与许可全文见 [third-party-notices.txt](app/public/third-party-notices.txt)，站点页脚链接到该文件。

[32_Mechanic_constraints_and_fact_tokens.md](32_Mechanic_constraints_and_fact_tokens.md) 记录机制约束和尚待游戏内核实的事项。更早的阶段记录在 git 历史中。

## 许可

本项目自己的代码和 `data/annotations/` 以 [MIT](LICENSE) 发布。游戏名称、效果文本与图片不在此授权内；第三方资料和字体遵循 [third-party-notices.txt](app/public/third-party-notices.txt) 所列的各自条款。
