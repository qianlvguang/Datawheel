# Datawheel (多模态视觉数据飞轮与工业级实物微调评测系统)

面向多模态大模型视觉对齐、细粒度图元定位 (Visual Grounding)、主体身份识别、参考图匹配与商品级实物合成评测的**程序化数据飞轮系统**。

> **当前迭代：v2** —— 10,000 条**全量渲染**的图文数据（每条样本 1 张实拍合成图 + 真值 BBox + 多类型 QA + 实体/底板隔离 split），并配套质检审计与训练导出工具链，可直接进入多模态中训练 / SFT 流水线。

---

## 🎯 系统定位与设计哲学

传统视觉微调面临**真实样本采集昂贵、边界框人工标注误差大、合成服装过于虚假（矢量课设简笔画）**等瓶颈。Datawheel 采取**素材供应链与资产台账先行**原则，结合**纯程序化数学透视合成**，实现 100% 绝对数学真理的零幻觉数据生成：

1. **绝对数学真理 (Zero Hallucination)**：坐标统一采用以**左上角为原点 (0, 0)** 的归一化相对坐标系，纵横范围均为 **0～1000**，格式严格为 `[ymin, xmin, ymax, xmax]`；BBox 由形变后的真实 Alpha 掩模反算，而非理论矩形。
2. **摄影级真实商品底板**：彻底摒弃低保真手绘矢量假衣服，接入真实电商实拍/影棚底料图（上装、裙装、箱包、鞋履、帽饰等），保留真实褶皱、面料纹理与光照。
3. **海量权威矢量图元**：覆盖全球标准国旗、国徽/纹章、地方行政区旗、商业品牌、高奢与 IP 品牌、动漫角色、亚文化符号。
4. **面向"聚焦能力"的课程设计**：不仅生成 caption，更生成**参考图匹配、困难负样本、证据不足、条件计数、空间关系**等能力导向任务，抑制名称/位置/模板捷径。

---

## 🚀 v2 数据集（当前主线，10,000 条）

### 1. 五阶段课程

| 阶段 | 样本数 | 能力目标 | 关键设计 |
|---|---:|---|---|
| `stage_a_geometry` | 1,000 | 颜色/几何/计数基础感知 | 程序化色块、三色旗、四宫格、向心圆盘；BBox 绝对精确 |
| `stage_b_single_element` | 4,000 | 单图元定位 + 属性识别 | 真实商品单图元贴附；按品类生成前胸/下摆/包盖/鞋帮等位置 |
| `stage_c_multi_element` | 2,500 | 多图元组合、计数、空间关系 | 2~3 个图元、5 类布局、非重叠约束、相对方位问答 |
| `stage_d_reference_match` | 1,500 | 参考图驱动的跨域身份匹配 | 顶部 2~4 张候选参考图 + 下方商品图；match / no_match / 困难负样本 |
| `stage_e_negative_evidence` | 1,000 | 正确否定与证据不足 | 无目标 clean、完全遮挡（uncertain）、高相似干扰图元 |

### 2. Split 与泛化隔离（实体级 + 底板级）

| split | 训练可见实体 | 训练可见底板 | 用途 |
|---|---|---|---|
| `train` | ✅ | ✅ | 训练 |
| `val` | ❌（held-out 实体） | ✅ | 模型选择 |
| `test_unseen_entity` | ❌（held-out 实体） | ✅ | 未见实体泛化 |
| `test_unseen_substrate` | ✅ | ❌（held-out 底板） | 未见商品底板泛化 |
| `test_unseen_both` | ❌ | ❌ | 双重分布外泛化 |

split 通过实体/底板 ID 的稳定哈希分桶实现，生成时直接按配额构造，保证 train 与各 test 轨的实体/底板集合无交叉。

### 3. 数据质量机制

- **保真底图排版**：非方形商品图按原始宽高比 letterbox，不再拉伸变形。
- **可印性质检**：对 1,500 张真实底板计算可印花区面积/纹理/明暗/肤色/背景占比，筛出 **447 张可印底板**，并按 easy/medium/hard 分档。
- **防语义错误区位词**：平铺底图使用「前胸/下摆/包盖/鞋帮/帽面」等工艺位置；真人上身图自动改用「画面相对位置」描述，避免"鞋子上胸前印花"这类错误断言。
- **小目标保底**：最小 BBox 面积重试（目标 ≥0.15% 画布），并通过 1.3× 扩张重渲染兜底。
- **物理融合**：单应性透视 + Sobel 折痕置换 + `Albedo × Shading` 混合；深色/繁复面料自动切换不透明塑胶浆模式保证可辨认度。
- **可复现**：每条样本由 `seed + sample_id` 派生确定性随机流；`image_sha256`、`content_hash`、`render_meta_json`、`quality_json` 全记录。
- **全量渲染**：10,000 条记录与 10,000 张图像一一对应（不再是 250 张预览图）。

### 4. QA 答案类型

每条样本 2~7 条 QA，答案类型覆盖：`bbox`（定位）、`name`（识别）、`color`、`count`（计数）、`relation`（方位）、`location`（工艺位置）、`yes_no`（存在性/是否匹配）、`uncertain`（证据不足）。每条 QA 附 `answer_bbox_1000`（如适用）与 `evidence_zh` 依据说明。

---

## 🧠 面向 Qwen3.5-27B 中训练（V6 通道）

v2 数据集已按 `~/Documents/Coding/CPT-SFT/training/qwen35_27b/` 的**实际中训练方案**（Qwen3.5-27B、ms-swift 4.3.2、V1–V5 通道、packed window 8192、GBS 32、S1/S2/S3 累计 LoRA）设计 V6 接入方案：

- **数据格式**：`messages / images / enable_thinking / sample_id / cate_id / variant`，`variant=6` 由现有插件自动映射为 `loss_V6`，无需改训练代码；图片路径相对 `/data/autovision-cfs/autovision-notebook`。
- **能力定位**：不重复 V1–V4 的通用 caption，而是补 27B 中训练最缺的**细粒度视觉证据能力**：小目标定位、多图参考匹配、相似干扰排除、证据不足拒绝、结构化描述、视觉事实一致性判断。
- **试点集**：`output/datawheel_v6_pilot/`（≈2,500 行：单图多轮 QA 1,200 / 结构化 caption 400 / 文本一致性 250 / 多图参考匹配 650；含远端上传包与 ms-swift 校验报告）。
- **balanced-v1 扩数据**：`output/datawheel_v6_balanced/`（union 43,893 行 = 单图 37,186 + 多图参考 6,707；S1 18,438 / S2 15,656 / S3 19,164；实测 token 份额 ~2.07%/2.00%/2.05%；validator critical=0；上传包 314MB）。
- **轻微旋转增强**：20% 样本（A/B/C/E，排除参考图匹配 D）做 ±3°~7° 旋转 + 中心裁切，bbox/QA 坐标按 mask 精确重算；工具 `tools/augment_v2_rotation.py`，对照图 `output/_debug/rotation_contact_sheet.jpg`。
- **配比方案**：见 [docs/MID_TRAIN_DATAWHEEL_PLAN.md](docs/MID_TRAIN_DATAWHEEL_PLAN.md)（按 S1/S2/S3 的 token 份额而非行数配比，light/balanced/aggressive 三档）。
- **文本描述规范**：以真实世界的物品、名称、颜色、位置、可见特征为主；不出现"程序化/矢量/基准模式名"等实现术语，不在 caption 里重复颜色、塞 bbox 或场景括注（bbox 放在 QA 中）。`generate.py v2` 会自动调用 `tools/normalize_dataset_language.py` 做清理；V6 构建后也建议执行一次。

---

## 🧰 工具链

| 工具 | 作用 |
|---|---|
| [`tools/build_asset_index.py`](tools/build_asset_index.py) | 离线构建 982 个前景图元的视觉索引（主导色/几何/dHash 近邻），供困难负样本选择 |
| [`tools/build_entity_name_table.py`](tools/build_entity_name_table.py) | 生成 582 条官方实体中英名表（271 国旗 / 121 国徽 / 190 地方旗），消除 raw code 与英文 fallback |
| [`tools/verify_entity_names.py`](tools/verify_entity_names.py) | 校验三大官方域 100% 中文命名覆盖 |
| [`tools/build_substrate_quality.py`](tools/build_substrate_quality.py) | 1,500 张真实底板的可印性/难度/区位索引（输出 `substrate_quality.json`） |
| [`tools/generate_datawheel_v2.py`](tools/generate_datawheel_v2.py) | v2 五阶段 10k 数据生成器（支持分片、预览、合并、报告、contact sheet） |
| [`tools/flywheel_audit.py`](tools/flywheel_audit.py) | 数据集质检审计：schema/bbox/图片/sha/重复率/split 泄漏/分布/小目标，输出报告三件套 |
| [`tools/export_training_data.py`](tools/export_training_data.py) | 按 split 导出 ShareGPT / ms-swift JSONL + dataset card + export manifest |
| [`tools/build_v6_single_image.py`](tools/build_v6_single_image.py) | v2 → V6 单图训练行（多轮 QA / 结构化 JSON caption / 文本一致性） |
| [`tools/build_v6_reference_rows.py`](tools/build_v6_reference_rows.py) | v2 stage_d → V6 多图参考匹配行（商品图 + 2~3 候选参考图，train split only） |
| [`tools/pack_v6_pilot.py`](tools/pack_v6_pilot.py) | 合并 V6 parts、统计 token/图片、生成远端上传包 |
| [`tools/build_v6_stage_mixtures.py`](tools/build_v6_stage_mixtures.py) | 按 light 档 r=3/2/4 生成 S1/S2/S3 stage parquet（重复副本、SAVE_STEPS 估算）并打包上传 |
| [`tools/build_v6_balanced_single.py`](tools/build_v6_balanced_single.py) | balanced 扩数据：37,186 行单图多任务行（8 cate 配额） |
| [`tools/build_v6_balanced_reference.py`](tools/build_v6_balanced_reference.py) | balanced 扩数据：6,707 行多图参考匹配行 |
| [`tools/assemble_v6_balanced.py`](tools/assemble_v6_balanced.py) | union → S1/S2/S3 stage 文件、validator、balanced 上传包 |
| [`tools/diagnose_and_refill_v6.py`](tools/diagnose_and_refill_v6.py) | **边查验、边造数（对接 `Coding/OPD` 与 `Coding/CPT-SFT`）**：对 v2/V6 候选回答做**实体知识缺口 vs BBox 坐标失准**四维解耦诊断，输出 `datawheel_refill_plan.json` 重采样倍率单与 MS-SWIFT V6 多模态 DPO/KTO/SFT 训练集 |
| [`tools/validate_swift_v6.py`](tools/validate_swift_v6.py) | V6 数据契约校验（schema / messages / 图片 / 长度估算 / cate 分布） |
| [`tools/build_visual_report.py`](tools/build_visual_report.py) | 生成 `output/report/index.html`：数据集总览 + 带 BBox 标注的样例画廊 + 配比/质检/产物索引 |
| [`tools/README.md`](tools/README.md) | 工具索引（资产构建 / v2 / V6 / 可视化） |
| [`generate.py`](generate.py) | 统一 CLI：历史四维度（gallery/contrastive/density/demo）与 v2 全量（`v2` / `datawheel10k`） |

---

## 📦 资产台账（v2 实测）

| 资产类别 | 规模与覆盖 | 来源与规范 |
|---|---|---|
| 官方国旗 / 国徽 / 地方旗 | **271** 国旗 + **121** 国徽/纹章 + **190** 地方行政区旗 | ISO 3166-1、Armorial of Sovereign States、各州/省/县官方旗帜（严格去重） |
| 商业品牌与商标 | **3,466** 通用品牌 + **100** 高奢品牌 + **100** 经典 IP 品牌 | Simple Icons 全量 + 高奢/IP 精选（纯矢量 SVG） |
| 动漫与角色 IP | **87** 款透明立绘（JUMP/原神/星铁/吉卜力/宝可梦全明星） | 官方立绘/精灵图，纯净 Alpha 通道 |
| 亚文化元素 | **115** 款（3D/扁平 Emoji、街头哥特、Y2K、Meme） | Fluent/Twemoji/game-icons/Slackmoji，含低分辨率参考图标记 |
| 真实商品底板 | 1,500 张实拍底料 → **447 张通过可印性质检** | 电商影棚实拍 / 时装周街拍（fashion_products / fashionpedia） |
| 外部独立评测基准 | 3 大基准（LogoDet-3K / QMUL-OpenLogo / ZACI-20） | 物理隔离，不混入训练，专做真实自然场景泛化 |

> 资产全景详见 [`assets/ASSET_CATALOG.md`](assets/ASSET_CATALOG.md)，结构化清单见 [`assets/manifests/`](assets/manifests/)。

---

## 🏗️ 目录结构

```
Coding/Datawheel/
├── README.md                     # 项目总览（本文件）
├── AGENTS.md                     # AI 编码代理工作约定与跨项目（CPT-SFT / OPD）互通说明
├── docs/                         # 文档
│   ├── README.md                 # 文档索引
│   └── MID_TRAIN_DATAWHEEL_PLAN.md  # Qwen3.5-27B 中训练 V6 数据方案
├── assets/                       # 多模态图元与底板资产库
│   ├── official_flags/           # 271 款 ISO 国旗 SVG
│   ├── official_emblems/         # 121 款国徽/纹章/组织徽记 SVG
│   ├── official_regional/        # 190 款地方行政区旗 SVG
│   ├── brand_logos/              # 3,466 通用品牌 + 100 高奢 + 100 IP 品牌
│   ├── character_ips/            # 87 款动漫透明立绘
│   ├── subculture_elements/      # 115 款亚文化样张
│   ├── commodity_substrates/     # 1,500 张真实商品底板（real_1500/）
│   └── manifests/                # 结构化清单 + 视觉索引 + 底板质检 + 实体名表
├── engine/                       # 几何、色彩、合成与知识扩写引擎
│   ├── compositor.py             # 保真排版、单应性、折痕置换、丝印/塑胶浆融合
│   ├── knowledge_expander.py     # 中英知识扩写（含 582 条官方实体名表接入）
│   ├── coords.py                 # 0~1000 相对坐标与 BBox 工具
│   └── ...                       # 历史 v1 引擎（geometry/builder/density 等）
├── synthesizer/                  # 标注与语义合成器（v1 遗留能力）
├── tools/                        # 工具（索引见 tools/README.md）
│   ├── build_visual_report.py    # 🖥️ 生成本地 HTML 核验页
│   ├── generate_datawheel_v2.py  # v2 五阶段 10k 生成器
│   ├── flywheel_audit.py         # 质检审计
│   ├── export_training_data.py   # 训练数据导出
│   ├── build_v6_*.py             # V6 中训练数据构建/组装
│   ├── build_asset_index.py      # 图元视觉索引
│   ├── build_substrate_quality.py# 底板可印性质检
│   ├── build_entity_name_table.py# 官方实体中文名表
│   └── verify_entity_names.py    # 命名覆盖率校验
├── output/                       # 生成产物（.gitignore 忽略，本地保留；索引见 output/README.md）
│   ├── report/index.html         # 🖥️ 本地核验可视化（双击打开）
│   ├── datawheel_v2/             # 10k 数据集 + images + audit + sft + _generation
│   ├── datawheel_v6_pilot/       # V6 试点 2.5k + upload + stage_files + parts + validation
│   ├── datawheel_v6_balanced/    # V6 balanced 43,893 union + S1/S2/S3 + upload
│   ├── legacy_v1/                # 历史 v1 演示产物与 10k caption 数据集
│   ├── audit/placement/          # placement 摆放审计（audit JSON / issues / 叠加图）
│   ├── placement/                # placement_optimizer 的 demo_* 交付示例
│   └── _debug/                   # 调试图与命名覆盖报告
├── generate.py                   # 统一生成 CLI（含 v2 全量模式）
├── pipeline.py                   # 历史流水线入口
└── requirements.txt
```

---

## 🖥️ 本地核验可视化

生成一个离线 HTML 页面，用于核对数据集统计、样例与 BBox 标注（无需服务器，双击/`open` 即可）：

```bash
.venv/bin/python tools/build_visual_report.py
open output/report/index.html
```

页面包含：数据集总览卡片、v2/V6 样例画廊（可按数据集/阶段/cate/split 过滤，BBox 叠加标注、点击放大）、
S1/S2/S3 中训练配比与 TRAIN_FILES 片段、质检/契约校验结论、产物索引与复现命令。

- `output/report/index.html`（**自包含，约 6MB**）：所有画廊图片以 base64 内嵌，可拷到任意目录/用任意浏览器打开；
- `output/report/index_light.html`（约 0.4MB）：图片用项目相对路径，仅适合在本项目目录内用浏览器直接打开；
- 重新生成：默认同时产出两份；`--no-embed` 只生成轻量版。

---

## ⚡ 快速开始

> 环境：项目自带 `.venv`（Python 3.14，numpy / opencv / pillow / resvg-py / pyarrow），无需联网。
> 所有命令均在 `Coding/Datawheel/` 下执行。

```bash
# 0) 资产品质索引（首次或资产变更后执行，约 20s）
.venv/bin/python tools/build_asset_index.py
.venv/bin/python tools/build_substrate_quality.py
.venv/bin/python tools/build_entity_name_table.py
.venv/bin/python tools/verify_entity_names.py

# 1) 全量生成 v2 10,000 样本（4 分片并行 + 自动合并，约 5~10 分钟）
.venv/bin/python generate.py v2
# 或直接调用生成器（可指定 --start/--end/--shards/--seed）
.venv/bin/python tools/generate_datawheel_v2.py --start 1 --end 10000 --shards 4

# 2) 快速预览（每阶段 2 张，带 BBox 调试图，几秒完成）
.venv/bin/python tools/generate_datawheel_v2.py --preview --out-dir /tmp/v2_preview

# 3) 数据集质检审计
.venv/bin/python tools/flywheel_audit.py \
    --dataset output/datawheel_v2/dataset.parquet --images-root . \
    --out output/datawheel_v2/audit/

# 4) 导出训练数据（ShareGPT / ms-swift，按 split 分文件）
.venv/bin/python tools/export_training_data.py \
    --dataset output/datawheel_v2/dataset.parquet \
    --out-dir output/datawheel_v2/sft/ --formats sharegpt,ms-swift --seed 42
```

### 历史版本（v1 演示流水线，仍可运行）

```bash
.venv/bin/python generate.py            # 一键生成 gallery/contrastive/density/demo 并汇总
.venv/bin/python generate.py gallery    # 官方 SVG 8 大认知任务画廊
.venv/bin/python tools/generate_10k_parquet.py  # v1 10k caption parquet（仅 250 张预览图）
```

---

## 🧾 v2 数据 Schema 摘要

`dataset.parquet` 主要列：

| 列 | 说明 |
|---|---|
| `sample_id` / `dataset_version` | 样本 ID / 版本号 |
| `task_stage` / `stage_title_zh` / `task_family` | 阶段、任务族 |
| `difficulty` / `split` / `domain` | 难度、数据划分、实体域 |
| `entity_ids_json` | 监督实体来源（domain + stem + role + 中英名） |
| `substrate_id` / `substrate_category_zh/en` / `substrate_source` | 商品底板与品类 |
| `placement_zone` / `print_technique_zh` | 工艺位置与印制工艺 |
| `bboxes_norm_1000` / `entities_json` | 正向实例 BBox 与实体明细 |
| `ref_candidates_json` | 参考图匹配阶段的候选参考框与正负角色 |
| `match_label` | `match` / `no_match` / `insufficient_evidence` / `not_applicable` |
| `caption_zh` / `caption_en` | 双语稠密描述 |
| `qa_pairs_json` | 多类型 QA（question/answer/answer_type/answer_bbox/evidence） |
| `image_path` / `image_sha256` / `image_width` / `image_height` | 图像与校验信息 |
| `render_meta_json` / `quality_json` / `content_hash` | 渲染参数、可见度/面积质检、内容哈希 |

---

## 🔬 验证与已知限制

- **验证**：所有工具均 `py_compile` 通过；v2 生成后由 `flywheel_audit.py` 对 schema、BBox、图片 sha、split 泄漏、分布与小目标做自动审计（报告见 `output/datawheel_v2/audit/`），本轮结果：**critical = 0**，warning 2 项（503 个小目标 0.1%~0.2%、QA 模板对重复 56.6%），另有 caption 完全/近重复 3.4%/3.5% 与程序化底板共享为 info，exit code 0。
- **人工抽检**：每阶段 4 个样本的 contact sheet 见 `output/datawheel_v2/contact_sheet.jpg`；D 阶段候选框与商品实例框一致性、候选 pane 区域校验 0 异常。
- **训练导出**：`export_training_data.py` 已产出 5 split × 2 格式（ShareGPT / ms-swift），每格式 **47,882 行**（QA 45,882 + dense caption 2,000），bbox 结构化行 12,895，全部 JSONL 逐行可解析、10,000 张图片引用 0 缺失。
- **已知限制**：
  1. 可印底板 447 张，长尾品类（裙装/裤装/大衣）覆盖仍少于上装/箱包/鞋履；
  2. 真人上身底图无法保证"服装部位"语义，已改用画面相对位置描述；
  3. 参考图匹配的困难负样本基于 dHash 视觉近邻，尚未引入更细的属性级对比；
  4. QA 为模板化生成，跨样本 exact pair 重复率偏高（56.5%），caption 完全重复 3.4%、归一化近重复 3.5%，后续需注入更多问法变体与样本特有细节；
  5. 当前数据飞轮闭环止于"生成→质检→导出"；真实 VLM 训练反馈/失败样本回流将在下一轮接入。
- **下一轮飞轮改进门禁（计划）**：`qa_pair_dup_rate ≤ 15%` 设为硬门禁；caption/图片近重复（pHash）纳入审计；`val↔train` 泄漏与 split 配额偏差纳入 CI；按 VLM 失败样本回流定向补数据。

---

## 📎 相关文档

- [Qwen3.5-27B 中训练 V6 数据方案](docs/MID_TRAIN_DATAWHEEL_PLAN.md)
- [资产全景台账](assets/ASSET_CATALOG.md)
- [v2 数据集报告](output/datawheel_v2/report.md)（生成后自动创建）
- [v1 10K 数据集报告](output/legacy_v1/DATASET_10K_REPORT.md)（历史）
- [Qwen-Image 2.1 图像编辑管线设计](docs/QWEN_IMAGE_2_1_PIPELINE.md)
- [AI 编码代理规范与跨仓（CPT-SFT / OPD）互通说明](AGENTS.md)
- [全域数据合成与双通道蒸馏监控台 HTML](../OPD/dashboard.html)（由 [`../OPD/build_global_dashboard.py`](../OPD/build_global_dashboard.py) 生成）
