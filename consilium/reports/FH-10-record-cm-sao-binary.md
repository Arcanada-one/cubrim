# FH-10 — record-aware CM для sao: первый measured #1 по типу binary

- **Card:** FH-10 (hypotheses / hypothesis_world_measurement, measure_date 2026-07-16)
- **Commit:** `944fe114fbe83093c6579581b4dde2b57eeb15a5` (research: add forced record-aware CM spike)
- **Bundle:** `cubr-fh10-944fe11.bundle`
- **Verdict:** **GO** (операторский floor 2026-07-16: GO только при честной победе над лидером типа)

## Механизм

sao (silesia) — звёздный каталог SAO: плотный массив 28-байтовых записей с
фиксированной раскладкой полей. Спайк `test_fh10_actual_file_spike` кодирует поток
record-aware CM-схемой (`candidate_mode=13`): контекст модели учитывает позицию байта
внутри 28-байтовой записи (столбцовая структура полей), вместо слепого
последовательного контекста. Round-trip обязателен: decode == input, cmp=0.

## Измерения (dev-ai, CUBR_THREADS=4, fail-closed контроллер)

### Target (sao, 7 251 944 B)

| rail | bytes | ratio |
|---|---|---|
| **FH-10 record-cm (width=28)** | **3 839 238** | **0.529408114569004** |
| live Cubrim rail (corrected CM19) | — | 0.624436 |
| baseline auto @944fe11 | 5 042 344 | 0.695309 |
| 7z LZMA2 -mx=9 | 4 413 926 | 0.608654176038866 |
| xz -9e | 4 425 664 | 0.610272776513442 |
| rar -m5 | 5 542 555 | 0.764285410918783 |

RT=OK, cmp=0. Кандидат бьёт лидеров файла (7z/xz) на ~13% отн.

### Full-24 (exact, 24/24 RT=OK cmp=0)

- mode `competitive-min(auto,record-cm)`: record-cm выиграл 1/24 (sao), остальные auto.
- total 72 987 700 / 314 749 364, world aggregate **0.23189197929562774**.
- Summary SHA256 `0ea25873542bb90bece852827d72845ddfb684ae160bc6f05d655ca80a7aff79`.

### Консервативный overlay против live rail (half-ULP floor, без округлённых фантомов)

- winning rows: 1 (sao, −689 137 B vs live rail).
- **binary-тип: 0.4713221075951619 против лидера 7z 0.5377525162660062 → Cubrim #1 по binary, −12.4% отн.**
- overall: 0.2205180148939869 (live 0.22270749319769523) — запас #1 растёт.
- Полный вывод: `cubr-master-audit/CUBR-0046/fh10-rank-overlay-20260716.txt`.

## Провенанс

- Контроллер: `fh10_load_gated_run.sh` SHA256 `1f35bbe6e07f3c76254a3968201406fb348688bea9f185dc3cd32e4ffc023c05`
  (load gate <12, paxbt=0, cubrim=0, fail-closed grep RT/cmp).
- Full24-раннер: `fh_full24_runner.py` SHA256 `6260463cb0cec2708078d8ac9ae9ebc0791e698a7f209d5af2648d3f4cde06f3`.
- DB backup перед транзакцией: `arcanada_cubrim-pre-FH10-full24-GO-20260716T132231Z.sql.gz`
  SHA256 `dfaa78c4a524e930d60bb77e5e3b23beb638c3e9f23c95e14f1c0bd98831e764`.

## Следствия

1. Первый per-type #1, добытый в очереди CUBR-0046 (text и exe пока NO-GO: FU-01, FH-07).
2. Record-aware контекст — подтверждённый рычаг для файлов с фиксированной шириной записи;
   кандидат на обобщение (авто-детект ширины записи) при интеграции в rail.
3. Интеграция в продовый rail — отдельная задача (карточка меряет candidate-rail;
   официальный world-benchmark обновится после интеграции схемы в cubrim-rs и remeasure).
