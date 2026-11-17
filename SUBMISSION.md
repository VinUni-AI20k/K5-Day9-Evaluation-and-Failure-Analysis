# Ná»™p bÃ i (háº¡n 23:59 cÃ¹ng ngÃ y)
PR tá»« `starter/d09` â†’ `main` cá»§a repo nhÃ³m. Cháº¥m commit cuá»‘i trÆ°á»›c 23:59; commit sau háº¡n khÃ´ng tÃ­nh.

## Core (nÃªn xong trÆ°á»›c 17:00)
- [x] `src/lab9/{stats,graders,evalset}.py` Ä‘Ã£ hoÃ n thÃ nh TODO M1â€“M4
- [x] `src/data/eval/eval_set_v1.jsonl` cÃ³ `failure_modes`, `labels_v1.json` tÃ¡ch riÃªng
- [x] `docs/failure_taxonomy.md`, `docs/trace_case.md` (1 case + regression test), `docs/judge_audit.md`, `docs/eval_card.md`, `docs/PRD_v1.1.md`
- [x] `src/reports/baseline_v1.json`, `eval_fixed.json`, `eval_seeded_regression.json` (sinh báº±ng script)
- [x] `harness_map.yaml` cÃ³ section `eval` (máº«u: `src/harness_map.eval.yaml`)
- [ ] Job `eval-gate` xanh; dÃ¡n output gate exit 1 cá»§a `seeded_regression` vÃ o mÃ´ táº£ PR

## Advanced / Expert (tá»›i 23:59)
- [x] `config/fm_map.yaml`, `config/metric_spec_v2.yaml` (slices, `pass_hat_5`, metric FM-08), `stats.pass_at_k/pass_hat_k`, `gate.slice_check`, `gate.integrity_check`
- [x] `src/data/eval/eval_set_v2.jsonl` + `labels_v2.json` (sinh báº±ng `evalset --v2 --build`)
- [x] `src/reports/baseline_v2.json` (sinh báº±ng script) â†’ job `eval-gate-v2` cháº¡y vÃ  xanh
- [ ] MÃ´ táº£ PR: output `lab9.mutation` (scorecard + `--aa`) vÃ  4 dÃ²ng `exit 1` cá»§a cÃ¡c trap
- [ ] `docs/eval_card.md` thÃªm má»¥c v2: ngÆ°á»¡ng chá»n tá»« A/A, slice nÃ o báº¯t lá»—i nÃ o, vÃ  giá»›i háº¡n cá»¡ máº«u (bug 1/3 seed khÃ´ng phÃ¡t hiá»‡n á»•n Ä‘á»‹nh vá»›i 5 seed)
