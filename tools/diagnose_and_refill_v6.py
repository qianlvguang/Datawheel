#!/usr/bin/env python3
"""Datawheel v2/V6 Closed-Loop Diagnostic & Targeted Refill Connector.

Bridges `Coding/Datawheel` with `Coding/OPD/multimodal_datawheel_bridge.py`:
  1. Reads Datawheel v2 records (from `output/datawheel_v2/dataset.parquet` or a JSONL
     shard) alongside VLM/API candidate responses (or synthesizes diagnostic probing
     candidates across Stage B/C/E to test Student knowledge & grounding).
  2. Runs `multimodal_datawheel_bridge.build_multimodal_flywheel_diagnostics_and_exports`
     to separate:
       - `knowledge_gap_entity` (Student sees the BBox, but doesn't know the entity/flag/brand)
       - `grounding_drift_bbox` (Student names the entity via shortcut, but BBox IoU < 0.5)
       - `visual_hallucination_negative` (Student hallucinates on Stage E clean/occluded items)
       - `spatial_or_count_error` (Student fails Stage C multi-element counting/relations)
  3. Emits:
       - `output/montessori_diagnostics/datawheel_refill_plan.json`: Domain & entity refill
         multipliers that directly tell Datawheel which domains/entities/substrates to
         oversample in the next flywheel round.
       - `output/montessori_diagnostics/vlm_datawheel_{sft,dpo,kto}.jsonl`: MS-SWIFT V6
         multimodal training files (`messages` + `images` + `cate_id` + `variant=6`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OPD_DIR = PROJECT_ROOT.parent / "OPD"
if str(OPD_DIR) not in sys.path:
    sys.path.insert(0, str(OPD_DIR))

from multimodal_datawheel_bridge import (  # noqa: E402
    build_multimodal_flywheel_diagnostics_and_exports,
    generate_demo_multimodal_probe_records,
)


def sample_v2_records_for_probing(
    parquet_path: Path,
    max_samples: int = 24,
) -> list[dict[str, Any]]:
    """Loads real `train` split rows from Datawheel v2 parquet and builds probing candidates."""
    import pyarrow.parquet as pq

    columns = [
        "sample_id",
        "task_stage",
        "split",
        "domain",
        "substrate_category_zh",
        "placement_zone",
        "bboxes_norm_1000",
        "entities_json",
        "qa_pairs_json",
        "image_path",
    ]
    table = pq.read_table(parquet_path, columns=columns)
    rows = table.to_pylist()

    probe_records: list[dict[str, Any]] = []
    count = 0
    for r in rows:
        if r.get("split") != "train":
            continue
        stage = r.get("task_stage")
        if stage not in ("stage_b_single_element", "stage_c_multi_element", "stage_e_negative_evidence"):
            continue
        qa_list = json.loads(r.get("qa_pairs_json") or "[]")
        entities_raw = json.loads(r.get("entities_json") or "[]")
        bboxes = json.loads(r.get("bboxes_norm_1000") or "[]")
        if not qa_list:
            continue

        entity_names = [
            str(e.get("entity_name_zh") or e.get("name_zh") or e.get("name") or "")
            for e in entities_raw
            if isinstance(e, dict)
        ]
        entity_names = [n for n in entity_names if n]

        gt = {
            "task_stage": stage,
            "domain": r.get("domain") or "official_flags",
            "cate_id": "misleading" if stage == "stage_e_negative_evidence" else "apparel",
            "substrate_category_zh": r.get("substrate_category_zh") or "商品底板",
            "placement_zone": r.get("placement_zone") or "正面",
            "entities": entity_names,
            "bboxes": bboxes,
            "is_negative_or_occluded": stage == "stage_e_negative_evidence" and not bboxes,
            "image_path": r.get("image_path") or "",
        }

        # Pick the primary QA pair as gold positive candidate
        q0 = qa_list[0]
        question_zh = str(q0.get("question_zh") or "请描述图中印花图案及其位置。")
        gold_answer_zh = str(q0.get("answer_zh") or "")
        if bboxes and "[" not in gold_answer_zh:
            b0 = bboxes[0]
            gold_answer_zh += f" 边界框坐标为 [{b0[0]}, {b0[1]}, {b0[2]}, {b0[3]}]。"

        probe_records.append(
            {
                "sample_id": r["sample_id"],
                "ground_truth": gt,
                "candidate": {
                    "question": question_zh,
                    "answer": gold_answer_zh,
                    "answer_type": q0.get("answer_type", "bbox"),
                    "influence_score": 0.062,
                },
            }
        )

        # Construct a controlled negative candidate (either knowledge gap or bbox drift)
        if stage == "stage_e_negative_evidence":
            neg_ans = "图中商品正面印有明显的品牌标识，边界框坐标为 [320, 320, 520, 520]。"
        elif count % 2 == 0 and bboxes:
            # Knowledge gap: right bbox, wrong entity name
            b0 = bboxes[0]
            neg_ans = f"图中商品{gt['placement_zone']}印有未知通用几何徽标，边界框坐标为 [{b0[0]}, {b0[1]}, {b0[2]}, {b0[3]}]。"
        else:
            # Grounding drift: right entity name, drifted bbox
            ent_str = "、".join(entity_names) if entity_names else "目标图案"
            neg_ans = f"图中商品印有{ent_str}，边界框坐标为 [10, 10, 120, 120]。"

        probe_records.append(
            {
                "sample_id": r["sample_id"],
                "ground_truth": gt,
                "candidate": {
                    "question": question_zh,
                    "answer": neg_ans,
                    "answer_type": "bbox",
                    "influence_score": -0.048,
                },
            }
        )

        count += 1
        if count >= max_samples:
            break

    return probe_records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-parquet",
        type=Path,
        default=PROJECT_ROOT / "output" / "datawheel_v2" / "dataset.parquet",
        help="Path to Datawheel v2 dataset.parquet (falls back to built-in demo if absent)",
    )
    parser.add_argument(
        "--candidates-jsonl",
        type=Path,
        default=None,
        help="Optional external VLM/API candidate responses JSONL",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "output" / "montessori_diagnostics",
        help="Output directory for refill plan & VLM DPO/KTO/SFT datasets",
    )
    parser.add_argument("--max-samples", type=int, default=24)
    parser.add_argument("--iou-threshold", type=float, default=0.50)
    args = parser.parse_args(argv)

    if args.candidates_jsonl and args.candidates_jsonl.exists():
        records = [
            json.loads(line)
            for line in args.candidates_jsonl.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        source_mode = "external_jsonl"
    elif args.dataset_parquet.exists():
        try:
            records = sample_v2_records_for_probing(args.dataset_parquet, max_samples=args.max_samples)
            source_mode = "datawheel_v2_parquet"
        except Exception:
            records = generate_demo_multimodal_probe_records()
            source_mode = "builtin_demo_fallback"
    else:
        records = generate_demo_multimodal_probe_records()
        source_mode = "builtin_demo"

    plan = build_multimodal_flywheel_diagnostics_and_exports(
        records=records,
        output_dir=args.output_dir,
        iou_threshold=args.iou_threshold,
    )
    plan["source_mode"] = source_mode
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
