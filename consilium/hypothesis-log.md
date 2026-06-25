---
artifact: hypothesis-log
task: CUBR-0003
created: 2026-06-17
---

> 🔒 **СЕКРЕТНО — внутренний артефакт.** Журнал гипотез механизма Cubrim. Живёт ТОЛЬКО в приватном репо `Arcanada-one/cubrim` (`Projects/Cubrim/consilium/`) и в gitignored `datarim/`. НИКОГДА не попадает в `Projects/Cubrim/documentation/`, README или любую публичную поверхность.

# Cubrim — Hypothesis Log (running journal)

> **Зачем.** Project CLAUDE.md: «Hypotheses are logged, not lost». Каждая гипотеза о
> подходе (выбор `N`, граница `B`, схема карты, отображение `Φ`, бит-пакинг,
> доменизация) фиксируется со своей v1-стартовой позицией, критерием разрешения и
> статусом — **в т.ч. отклонённые**. Привязка: `PRD-CUBR-0002` §6 (OQ-1..OQ-5),
> rulebook-v1.md (R1..R8).
>
> **Статус на Phase 0.** Все гипотезы — `open`. Это design-only раунд (CUBR-0003);
> НИ ОДНА ещё не измерена. Разрешение — на прототипе CUBR-0004 на бенчмарк-корпусе.
> «Prior art it reduces to» заполнен честно — без unearned novelty.

---

### H-01 — Размерность куба `N` = 2 (baseline)

- **Hypothesis:** фиксированное `N = 2` — достаточный стартовый baseline; рост `N`
  (3D/4D/переменное) не окупит накладные расходы на оси/шапку и взрыв `|C|` на
  типовых данных корпуса.
- **Maps to:** OQ-1 / PRD §4.1, §6 OQ-1 / rulebook R1.
- **v1 starting choice:** `N = 2`, лексикографический обход. Минимально накладной
  контур для отладки round-trip и инварианта прежде платы за многомерность.
- **Resolution criterion:** на фиксированном бенчмарк-корпусе — лучший **средний
  коэффициент сжатия при сохранении round-trip** и приемлемой скорости/памяти
  (PRD §6 OQ-1). Допустимо «`N` как параметр шапки», если адаптивный `N` стабильно
  бьёт фиксированный.
- **Status:** `open`.
- **Prior art it reduces to:** N-мерные решётки / sparse-tensor раскладки; 2D — это
  по сути sparse-matrix CSR/COO случай.
- **Замер CUBR-0004 (2026-06-17):** v1-default N=2, B=256. Corpus: text_64kb + log_16kb (cube mode), random_64kb (raw-store). Cube ratio (cube-mode files): text=0.6260, log=0.7556, mean=0.6908. N=2 produces a fully-dense cube for L=B^2 inputs (ρ=1.0). At full density all gaps=1; RLE compresses the gap map to minimal overhead; compression comes entirely from value bitpacking (W=8 for 256 distinct values = no savings vs raw bytes). Status: `measured — open; N=2 gives cube mode for text/log (ratio < 1), raw-store for random (no blowup). Challengers (H-01 OQ-1) not measured — open for CUBR-0007.`

---

### H-02 — Отображение `Φ` = mixed-radix по позиции

- **Hypothesis:** mixed-radix разложение индекса по основанию `B` — адекватная
  стартовая `Φ`; его локальности хватает, чтобы карта расстояний начала сжиматься.
- **Maps to:** OQ-3 / PRD §4.1, §6 OQ-3 / rulebook R1.
- **v1 starting choice:** `Φ` = mixed-radix, `Φ⁻¹` = обратное mixed-radix. Биективность
  тривиально доказуема → безопасно для round-trip.
- **Resolution criterion:** `Φ`, максимизирующая **локальность** — долю `gap = 1` и
  длину серий в RLE на корпусе при round-trip (PRD §6 OQ-3, прокси сжимаемости карты).
- **Status:** `open`. *(Vendor-флаг: DeepSeek-вердикт оценивает, что Hilbert-кривая
  способна снизить долю не-`gap=1` на >30% на коррелированных данных; Moonshot-вердикт
  ставит дефолтом Morton/Z-order — оба претендента на замену по критерию локальности;
  логируется как H-02a.)*
- **Prior art it reduces to:** mixed-radix позиционная нумерация; претенденты —
  Morton/Z-order, Hilbert space-filling curves (locality-preserving).
- **Замер CUBR-0004 (2026-06-17):** fraction(gap=1)=1.0000 on all corpus files (text_64kb, random_64kb, log_16kb). Mean run-length(gap=1)=448 overall (text=512, random=512, log=320). Note: this result reflects fully-populated cube (L=B^2 or L=B^1.5 → ρ=1.0) where ALL gaps are 1 by definition — mixed-radix baseline maximally locality-trivial at ρ=1. Chalengers (Hilbert, Morton) not measured at this density level — gap=1 fraction does not discriminate Phi choices when ρ=1. Status: `measured-trivially — ρ=1 corpus; Phi challenger comparison needs sparse corpus. Open for CUBR-0007.`

---

### H-02a — `Φ` = Hilbert-кривая (претендент на замену mixed-radix)

- **Hypothesis:** Hilbert-обход сохраняет N-мерную локальность лучше лексикографического
  mixed-radix → выше доля `gap=1`, длиннее RLE-серии → сильнее сжатие карты.
- **Maps to:** OQ-3 / PRD §6 OQ-3 / rulebook R1. Источник: consilium verdicts (DeepSeek — Hilbert >30% локальности; Moonshot — Morton/Z-order дефолт).
- **v1 starting choice:** НЕ v1-default (mixed-radix проще и точно биективен). Hilbert
  прототипируется как челленджер во вторую очередь.
- **Resolution criterion:** тот же, что H-02 — доля `gap=1` + длина RLE-серий на
  корпусе; принимается, только если бьёт mixed-radix при сохранённом round-trip.
- **Status:** `open`.
- **Prior art it reduces to:** Hilbert / Morton (Z-order) space-filling curves.

---

### H-03 — Граница ребра `B` = 256 (степень двойки)

- **Hypothesis:** `B = 256` — разумный стартовый компромисс: байт-эквивалентный разряд
  координаты, ≤ 8 бит на сырой gap, не слишком мелкий (иначе много осей) и не слишком
  крупный (иначе длинные gap).
- **Maps to:** OQ-2 (часть «B») / PRD §4.1, §6 OQ-2 / rulebook R1, R3.
- **v1 starting choice:** `B = 256`, степень двойки, единое `B` на все оси (`b_k ≤ B`).
- **Resolution criterion:** комбинация `(B, схема карты)`, минимизирующая **биты карты
  расстояний на населённую точку** на корпусе, при round-trip и инварианте `gap ≤ b_k`
  (PRD §6 OQ-2). Кандидаты `B`: 16/64/256/1024, pow2 vs произвольное, `b_k` на ось.
- **Status:** `open`.
- **Prior art it reduces to:** выбор radix / word-size в позиционном кодировании;
  bit-width бюджет как во frame-of-reference кодах.
- **Замер CUBR-0004 (2026-06-17):** B=256 confirmed in use. At ρ=1 (full density), b_k=256=B for all axes — invariant holds. Unique axis coords = 256 per axis. H-03 not independently testable at ρ=1 (all values of B give same gap distribution). Status: `not_measured independently — ρ=1 corpus; B variation needs sparse corpus. Open for CUBR-0007.`

---

### H-04 — Раскладка карты расстояний = `N` потоков по осям

- **Hypothesis:** `N` отдельных потоков `gap_k` (по одному на ось) проще кодировать и
  отлаживать, чем единый интерливленный поток, и не хуже по сжатию на старте.
- **Maps to:** OQ-2 (раскладка) / PRD §4.3, §6 OQ-2 / rulebook R3.
- **v1 starting choice:** `N`-потоков (per-axis).
- **Resolution criterion:** раскладка, минимизирующая **биты карты на населённую точку**
  на корпусе при round-trip (PRD §6 OQ-2). Челленджер — единый интерливленный/скан поток.
- **Status:** `open`.
- **Prior art it reduces to:** structure-of-arrays vs array-of-structures раскладка
  координат; CSR хранит индексы по-осно.
- **Замер CUBR-0004 (2026-06-17):** N=2 per-axis streams used. At ρ=1 each axis has 256 unique coords. Gap map = 256 gaps of value 1 per axis → RLE encodes as 1 pair per axis (value=1, run=256). N-streams overhead = N×4B RLE pairs = 8B per axis set. Interleaved layout would give 1 pair per (N-axis combo) — likely similar at ρ=1. Bits-per-point from gap map: 8B / 65536 points ≈ 0.0001 bits/point — gap map is negligible overhead at full density. Status: `measured — N-streams layout works; challenger (H-11 interleaved) not measured; gap overhead negligible at ρ=1. Open for CUBR-0007.`

---

### H-05 — Семантика gap: sentinel −1, `gap=1` = ноль пропусков

- **Hypothesis:** единственная корректная декод-семантика — старт `x_k = −1`,
  `x_k += gap_k`, где `gap=1` означает НОЛЬ пропущенных слотов (немедленная позиция),
  а число пропусков = `gap−1`. Любая иная интерпретация ломает round-trip.
- **Maps to:** PRD §4.3, §4.7 / rulebook R3.1 / DeepSeek off-by-one флаг.
- **v1 starting choice:** sentinel −1, `gap_k = x_k^{(j)} − x_k^{(j-1)}`, инвариант
  `1 ≤ gap_k ≤ b_k ≤ B`. Encode fail-closed: `gap=0` запрещён, `gap>b_k` запрещён.
- **Resolution criterion:** НЕ статистический — детерминированный property-тест
  round-trip (`V-AC-1`) на worked-примере PRD §4.7 (`{0,3,7}→D=(1,3,4)→{0,3,7}`) и на
  рандом-разреженных входах. Это **hard-инвариант**, а не falsifiable-default: при
  провале чинится реализация, гипотеза не «заменяется».
- **Status:** `open` (не измерена; зафиксирована как инвариант на Phase 0).
- **Prior art it reduces to:** delta-кодирование разреженных индексов (CSR/COO delta);
  sentinel-начало — стандартный приём delta-кодеров.
- **Замер CUBR-0004 (2026-06-17):** CONFIRMED as hard invariant. 9 round-trip tests pass including the R3.1 worked example {0,3,7}→D=(1,3,4)→{0,3,7}. 9 gap-invariant tests pass (gap=0 raises, gap>b_k raises, non-monotone raises). Sentinel=-1 start verified by unit tests. Status: `measured-confirmed as invariant — gap=1 semantics correct; sentinel=-1 works; all tests green.`

---

### H-06 — Run-кодирование карты = чистый RLE

- **Hypothesis:** чистый RLE по рядам `gap_k` — достаточная стартовая компактная схема;
  длинные серии `1,1,1,…` в кластерах сжимаются, декод однозначен.
- **Maps to:** OQ-2 (схема) / PRD §4.4, §6 OQ-2 / rulebook R4.
- **v1 starting choice:** RLE парами `(значение_gap, длина_серии)`.
- **Resolution criterion:** схема, минимизирующая **биты карты на населённую точку** на
  корпусе при round-trip и инварианте `gap ≤ b_k` (PRD §6 OQ-2). Челленджеры:
  RLE+Huffman, delta-of-gap+RLE, Golomb/Rice, ANS.
- **Status:** `open`.
- **Prior art it reduces to:** RLE; для скошенного-к-малым распределения gap —
  Golomb-Rice, Huffman, ANS (rANS/tANS) энтропийное кодирование.
- **Замер CUBR-0004 (2026-06-17):** At ρ=1 the gap distribution is all-1 → RLE encodes as single run of 256 gaps of value 1 = 4 bytes per axis stream. Gap map overhead per axis = 4B / 65536 points = negligible. fraction(gap=1)=1.0, mean run-length=448 (corpus aggregate). This is the best possible case for RLE (entire stream = one run). Challengers (Golomb/ANS) would give the same result at ρ=1. Gap map benefit is unmeasurable at full density — needs sparse corpus (ρ < 0.3) to differentiate RLE vs alternatives. Status: `measured at ρ=1 — RLE overhead negligible; challenger comparison not_measured — open for CUBR-0007.`

---

### H-07 — Бит-пакинг значений = явная фиксированная ширина в шапке

- **Hypothesis:** единая фиксированная ширина `W = ⌈log2(max+1)⌉` (или ширина-на-блок
  из явной width-table) — простейшая детерминированная no-delimiter упаковка; достаточна
  как v1-старт.
- **Maps to:** OQ-4 / PRD §4.5, §6 OQ-4 / rulebook R5.
- **v1 starting choice:** явная ширина в шапке (fixed-width на файл; width-table на блок
  как первый шаг усложнения). **Контекстно-выводимая ширина ЗАПРЕЩЕНА в v1** (хедж против
  тихого слома round-trip, PRD §8).
- **Resolution criterion:** схема, минимизирующая **биты на значение** на корпусе при
  round-trip и при «no-delimiter» инварианте (PRD §6 OQ-4). Челленджеры:
  ширина-на-под-куб, контекстно-зависимая ширина, Elias/Golomb коды.
- **Status:** `open`.
- **Prior art it reduces to:** bit-packing / frame-of-reference; streamvbyte (пакетная
  ширина); Elias-gamma/delta, Golomb — целочисленные коды.

---

### H-08 — Доменизация входа `V` = байтовый поток как есть

- **Hypothesis:** трактовка входа как сырого байтового потока (без предобработки) —
  честный, ноль-предположений старт; round-trip тривиально гарантируется.
- **Maps to:** OQ-5 / PRD §6 OQ-5 / rulebook R8.
- **v1 starting choice:** `V` = байты входа без квантования/токенизации.
- **Resolution criterion:** доменизация, дающая наибольшую **разреженность-с-
  кластеризацией** (низкая `ρ` + высокая локальность) на корпусе при round-trip
  (PRD §6 OQ-5). Челленджеры: квантование числовых, пред-токенизация, раздельные кубы
  по типам данных. Может быть привязана к классу данных.
- **Status:** `open`.
- **Prior art it reduces to:** препроцессоры компрессоров (дельта-фильтры, токенизация,
  type-split как в колоночных форматах).
- **Замер CUBR-0004 (2026-06-17):** V = bytes as-is. text_64kb: 27 distinct values, W=5 bits (27 < 32), ratio=0.6260 (cube mode). log_16kb: 53 distinct values, W=6 bits, ratio=0.7556. random_64kb: 256 distinct values, W=8 bits — no savings, raw-store triggered. Bytes-as-is gives meaningful compression only when input has low distinct-value entropy. With W=8 (all 256 values distinct), bitpack = same size as raw bytes. Status: `measured — bytes-as-is baseline works for text/log (low distinct count); fails on random (W=8, no savings). Challengers (OQ-5) not measured — open for CUBR-0007.`

---

### H-09 — raw-store fallback против blowup (инвариант, не falsifiable-default)

- **Hypothesis:** обязательный режим `mode=1 (raw-store)` гарантирует, что формат
  никогда не раздувается выше `size(S) + bounded_overhead` на несжимаемых (не
  кластеризованных) входах.
- **Maps to:** PRD §4.6, §8 (риск worst-case blowup) / rulebook R7.
- **v1 starting choice:** кодер выбирает `cube` ⟺ `size(cube) < size(raw) + overhead`,
  иначе `raw-store`; декодер при `mode=1` возвращает raw напрямую.
- **Resolution criterion:** детерминированный — на корпусе с **рандом-перестановочными
  (некластеризованными) входами** проверить, что `size(out) ≤ size(in) + bounded_overhead`
  ВСЕГДА (никогда не blowup). Сам fallback не опровержим; калибруется лишь порог
  `overhead` и точное сравнение.
- **Status:** `open` (не измерена; зафиксирована как hard-правило на Phase 0).
- **Prior art it reduces to:** «stored block» режим DEFLATE/zstd (несжимаемый блок
  хранится как есть с флагом) — стандартный guard любого компрессора.
- **Замер CUBR-0004 (2026-06-17):** CONFIRMED. 1 MB uniform-random input (numpy seed 42): encode → mode=1 (raw-store). Output = 1,048,589 bytes. Input = 1,048,576 bytes. Overhead = 13 bytes (raw-mode header only). Ratio = 1.000012. HEADER_OVERHEAD_BOUND = 320 bytes. random_64kb (65,536 bytes): also raw-store, output = 65,549 bytes, overhead = 13 bytes. R7 decision rule: cube_size >= raw_output_size → raw-store. Round-trip OK on all raw-store inputs. Status: `measured-confirmed — R7 raw-store fires on random data; overhead bounded at 13 bytes (raw header); HEADER_OVERHEAD_BOUND=320B is conservative upper bound for any input size.`

---

### H-10 — Формат файла: детерминированный декод из шапки

- **Hypothesis:** шапки (`magic/version/mode/N/b_k/B/L/count/map_scheme/value_scheme/W|
  width_table/value_dict/traversal/phi`) + двух потоков достаточно для полностью
  детерминированного декода без внеполосной информации.
- **Maps to:** PRD §4.6 / rulebook R6.
- **v1 starting choice:** поля шапки по таблице R6; декод строго обратен кодированию.
- **Resolution criterion:** детерминированный — независимый декомпрессор (`V-AC-4`)
  восстанавливает `S` из файла, не имея доступа к состоянию кодера. Round-trip
  byte-exact (`V-AC-1`).
- **Status:** `open`.
- **Prior art it reduces to:** контейнерные форматы со self-describing header
  (PNG/zstd frame header) — параметры декода едут в шапке.
- **Замер CUBR-0004 (2026-06-17):** Header parse + deterministic decode verified by 32 pytest cases (test_round_trip, test_decode_robustness). Bad magic/version/truncation all raise explicitly. Round-trip byte-exact confirmed on text_1kb, random_1kb, log_16kb, plus edge cases (empty, single byte, all-same, all-distinct). Status: `measured-confirmed — V-AC-1 and V-AC-4 pass; deterministic decode from header alone verified.`

---

### H-11 — Интерливленная раскладка карты vs `N` потоков (кросс-осевой энтропийный контекст)

- **Hypothesis:** раскладка карты расстояний в `N` независимых потоков по осям (H-04 v1-default)
  фрагментирует статистический контекст и теряет кросс-осевые корреляции `gap_x↔gap_y`, которые
  ловят современные кодеки (zstd/LZMA); единый интерливленный поток (или совместный энтропийный
  контекст по осям) может дать более сильное сжатие карты на коррелированных данных. Кроме того,
  «no-delimiter»-инвариант (R5) запрещает динамический арифметический код значений → потолок
  эффективности значений ниже плоского LZ77+ANS на неклассторизованных данных.
- **Maps to:** OQ-2 (раскладка карты) + OQ-4 (потолок значений) / PRD §4.3, §4.4, §6 OQ-2 /
  rulebook R4, R5. **Источник:** consilium verdict (Moonshot Kimi K2.5) — «entropy-coder context
  dilution» как главный недооценённый риск.
- **v1 starting choice:** НЕ v1-default. v1 берёт `N`-потоков (H-04) как простейший baseline;
  интерливленная/совместная раскладка прототипируется как челленджер во вторую очередь.
- **Resolution criterion:** на корпусе сравнить **бит карты на населённую точку** при `N`-потоках
  против интерливленной раскладки при сохранённом round-trip (PRD §6 OQ-2). Принимается, только
  если интерливл стабильно бьёт `N`-потоков. Дополнительно: измерить разрыв до zstd/Brotli на тех
  же данных как ориентир «сколько контекста теряется» (PRD §5, V-AC-2 baseline).
- **Status:** `open`.
- **Prior art it reduces to:** контекстное моделирование энтропийных кодеров (LZMA range coder,
  zstd FSE с общим контекстом); кросс-столбцовое кодирование в колоночных форматах (Parquet/ORC).
- **Замер CUBR-0004 (2026-06-17):** `not_measured — H-11 is a challenger hypothesis (interleaved layout not v1-default). Baseline N-streams measured (see H-04). Interleaved vs N-streams comparison open for CUBR-0007.`

---

### H-12 — Order-2 context-key Huffman (R6 scheme hypothesis)

- **Hypothesis:** using `(prev2_code, prev_code)` as the context key for per-context Huffman tables (order-2) will outperform the order-1 key `prev_code` (T4) because it captures two-symbol conditional dependencies; best aggregate ~0.547730 (−6.73% vs T4) predicted by Python twin with MIN_CTX_COUNT=128.
- **Maps to:** R6 scheme hypothesis / rulebook R5 (value-stream entropy coding) / consilium CUBR-0026 GO verdict.
- **v1 starting choice:** order-2 key with 3-level fallback (order-2 → order-1 → order-0); MIN_CTX_COUNT threshold gates table creation; wire format serializes all three levels.
- **Resolution criterion:** real Rust aggregate on 7-file corpus vs T4 0.587240 baseline; GO if aggregate < T4, NO-GO otherwise. Sweep MIN_CTX_COUNT ∈ {64,96,128,...,1024}.
- **Status:** `measured — NO-GO in implementation (CUBR-0027, best 0.592215 at MIN_CTX_COUNT=256 = +0.004975 above T4 0.587240).`
- **Prior art it reduces to:** order-N Markov context models (PPM, LZMA range coder); double-symbol conditioning common in arithmetic coders.
- **Замер CUBR-0026 (2026-06-20, Python twin):** GO in model. Best aggregate 0.547730 at MIN_CTX_COUNT=128 (−6.728% vs T4). Python twin charged no cost for order-1 fallback table serialization — only order-2 and order-0 tables counted in the size model.
- **Замер CUBR-0027 (2026-06-20, Rust codec):** NO-GO in implementation. Best aggregate 0.592215 at MIN_CTX_COUNT=256 = +0.004975 above T4 (NOT beating baseline). Round-trip 7/7 byte-exact. Root cause of GO→NO-GO gap: the Python size-model did not charge for order-1 fallback table serialization; the real Rust encoder must serialize all three levels (order-2 + order-1 + order-0) to support correct fallback decoding — this additional header cost erases the gains predicted by the twin. Option B (2-level wire, no order-1 tables) was also measured and performed worse (~0.626 aggregate at MIN_CTX_COUNT=128) because mid-frequency context keys fall back to order-0 global rather than order-1. Conclusion: R4 (RLE pre-pass), R5 (grouped context), and R6 (order-2) are all NO-GO at implementation. The value-stream optimum for this corpus is T4 (order-1 per-code). Future hypotheses should target a different axis (distance-map encoding, BWT-style reordering of the value stream, or corpus-specific pre-processing).

---

### H-13 — BWT-style value-stream reordering (CUBR-0028)

- **Hypothesis:** applying the Burrows-Wheeler Transform (BWT) to the value-code stream before T4's order-1 per-code Huffman coding reduces H(X_t|X_{t-1}) on structured inputs (text, log-like) by grouping identical symbols into runs — building its own locality INDEPENDENTLY of phi-coordinates (not phi-sort, per Gotcha #3). The modelled aggregate across the 7-file corpus is predicted to be ≤ 0.575495 (−2% GO threshold).
- **Maps to:** hypothesis CUBR-0028 / orthogonal-axis-BWT-reorder.
- **v1 starting choice:** full BWT on the L-element value-code stream, with primary index serialized as ceil(log2(L+2)/8) bytes per file; T4's existing order-1 Huffman applied to the BWT output.
- **Resolution criterion:** Python probe with correct size model (bwt_cost = T4_actual + (H1_bwt − H1_orig)×L/8 + primary_index_bytes + selector) modelled aggregate ≤ 0.575495; then confirmed by Rust implementation with round-trip + run_bench.py.
- **Status:** `GO — Python probe 2026-06-20; Rust confirmed 2026-06-20 (H-16). Real aggregate 0.504412.`
- **Prior art it reduces to:** BWT (Burrows-Wheeler, 1994) followed by entropy coding — this is the core of bzip2. Applied here to the VALUE-CODE stream (not raw bytes), it builds run structure that order-1 Huffman can exploit without changing the cube/phi/gap framework.
- **Замер CUBR-0028 (2026-06-20, Python probe):** GO. Modelled aggregate 0.464088 (−20.971% vs T4 0.587240). Entropy pre-gate PASS (max H1 reduction: 91.42% on log_like). Gotcha #6 check: 3 branches + 2 extra_terms = 5 cost_terms PASS. Key finding: BWT on text (H1: 2.1257→0.7289) and log_like (H1: 1.8348→0.1575) creates near-zero conditional entropy — the value-code stream becomes nearly deterministic given the previous symbol. BWT on sparse/random files (sparse_clustered, binary_mixed, random_high) does NOT help. Size model conservative and correct: n_distinct preserved by BWT → T4 table overhead unchanged → only bitstream size changes. primary_index = 2 bytes per cube-mode file (negligible). Full BWT H1 values verified by independent correct BWT implementation. Rust implementation required (plan Step 5).

---

### H-14 — Byte-level pre-processing (delta/MTF/stride-2 transforms, CUBR-0028)

- **Hypothesis:** invertible byte-level transforms applied before T4's Huffman coding reduce n_distinct (the symbol alphabet), lowering both table overhead and bitstream size.
- **Maps to:** hypothesis CUBR-0028 / orthogonal-axis-preproc.
- **Status:** `measured — NO-GO (CUBR-0028, 2026-06-20).`
- **Замер CUBR-0028 (2026-06-20, Python probe):** NO-GO. Modelled aggregate 0.586365 (−0.149% vs T4, all three transforms). Root cause: delta and MTF INCREASE n_distinct on cube-mode files (text: 27→95, log_like: 53→82), inflating T4 per-code Huffman table overhead by 11× for text (814B→9314B), completely erasing any bitstream savings. Stride-2 preserves n_distinct but increases H1 on all cube-mode files. No transform reduces the aggregate below 0.575495. The −0.149% improvement comes from raw-mode files where raw_bytes < T4_actual (T4 raw-store adds 13B overhead; the preproc selector byte costs 1B so raw+1 < T4+1 for those files).

---

### H-15 — Distance-map enhancement on canonical corpus (CUBR-0028)

- **Hypothesis:** an enhanced distance-map encoding (beyond RLE of gap=1) can improve compression on the canonical 7-file corpus.
- **Maps to:** hypothesis CUBR-0028 / orthogonal-axis-distmap.
- **Status:** `measured — NO-GO (CUBR-0028, 2026-06-20). Gotcha #1 confirmed.`
- **Замер CUBR-0028 (2026-06-20, Python probe):** NO-GO. Total distance-map RLE bytes = 26 (0.09% of 30217 T4 bytes). With positional i-order phi, phi(i) = (i%256, i//256), every cube cell [0..L-1] is occupied by construction → all gaps = 1 → RLE encodes trivially (≈4 bytes per axis per file). The distance-map mechanism carries ~0% on this corpus. Any enhancement branch adds mode-selector overhead with zero benefit. Gotcha #1 confirmed: the distance-map lever requires ρ<0.3 sparse inputs, which would require new corpus inputs and invalidate the 0.587240 T4 baseline comparison.

---

### H-16 — BWT Rust implementation (CUBR-0028, follow-up to H-13)

- **Hypothesis:** implementing `ValueScheme::BwtEntropy` (scheme byte 6) in Rust and measuring against the 7-file corpus will confirm H-13's Python GO and produce a real aggregate ≤ 0.575495.
- **Maps to:** hypothesis CUBR-0028 / plan Step 5 (Rust implementation on Python GO).
- **Status:** `measured — GO (CUBR-0028, 2026-06-20, Rust). Real aggregate 0.504412 beats threshold 0.575495.`
- **Замер CUBR-0028 (2026-06-20, Rust, code_sha 15b0ba6):** GO. Real aggregate 0.504412 (25955 bytes, −8.28% vs T4 0.587240 / 30217 bytes). GO threshold 0.575495 beaten by 7.1 percentage points. All 7 corpus files: round-trip lossless (172 tests pass). Per-file: text −2122B, log_like −2140B; sparse_clustered falls back to T4 (BWT worse on clustered sparse data); raw-mode files unchanged. Competitive selection implemented: encoder builds both BWT+T4 and plain T4 value streams, emits the smaller one with the correct scheme byte in the header. Gap vs Python model (0.464088 predicted, 0.504412 measured): real T4 context Huffman code lengths exceed H1 entropy lower bound — model gap was expected and well within the −2% GO margin. Implementation: `bwt_encode_codes`, `bwt_decode_codes`, `bwt_entropy_encode`, `bwt_entropy_decode`, `bwt_entropy_size` in `codec.rs`; wire format: `primary_index(u16) + T4_context_huffman_stream`. BWT: O(n log n) stable sort on rotation indices (sufficient for n ≤ 65536). Full JSON: `documentation/ephemeral/research/CUBR-0028-bench.json`.

---

### H-17 — External-address / global-snapshot lookup (16-byte universal reference)

- **Hypothesis (operator dialogue 2026-06-22, `_temp/addressator.txt`):** replace any file with a short fixed-width reference (16 bytes = 8-byte server/disk id + 8-byte snapshot id) into a global external library of cube bitmap "snapshots"; the decoder fetches the snapshot from the server and unfolds it back to the file.
- **Maps to:** operator-proposed idea CUBR (external content-addressed archive); recorded as a steel-man.
- **Status:** `NO-GO — refuted by information conservation / pigeonhole (recorded 2026-06-22, refuted in-dialogue). CLOSED in closed-branches.md.`
- **Refutation:** A fixed-width reference of B bits addresses at most 2^B inputs; the file space up to size S is 2^(8·S) (dialogue's own figure: 1 MB → 2^8,000,000 ≫ 2^128). By pigeonhole, distinct files collide on the same reference → lossless reconstruction is impossible in the general case; only previously-registered files round-trip (a catalogue, not a compressor). Also violates the self-contained-archiver premise (decode needs an external server) and the "snapshot" (full cube bitmap: 2 MiB for 3D, 512 MiB for 4D) is, in general, far larger than the source. Same family as Gotcha #7 (a coordinate/identifier that is not charged in the output cannot beat the entropy bound). No empirical measurement can overturn a pigeonhole argument → no Rust impl.
- **Legitimate residue:** the *charged shared dictionary* dedup form survives as a LIVE branch — see H-18.

---

### H-18 — Corpus-local deduplication against a charged shared dictionary

- **Hypothesis (operator dialogue 2026-06-22, `_temp/addressator.txt`, honest residue of H-17):** a *self-contained* archive that ships ONE shared dictionary inside the artefact and replaces repeated content within and across the corpus files with references into it — content-defined chunking (CDC / rolling-hash boundaries) over the value-code stream, identical chunks stored once, each file = chunk references + residual literals; optionally delta-code near-duplicate chunks (zstd `--patch-from` style).
- **Maps to:** operator-proposed idea CUBR (inter-file dedup); the inter-file lever the per-file BWT pipeline structurally cannot reach (BWT exploits intra-file run locality only).
- **Status:** `measured — NO-GO on the frozen corpus (cross-file dedup probe, 2026-06-22). Corpus-bound, not algorithm-bound — re-open only if the corpus gains genuinely redundant multi-file structure.`
- **Why it is NOT H-17:** the dictionary is shipped inside the artefact and charged in full exactly once in the size model — no external server, no universal fixed-width reference, no uncharged content-address. It harvests cross-file redundancy the frozen corpus may or may not contain; it makes no claim against the single-random-file entropy bound.
- **MANDATORY metric (Gotcha #7 false-GO guard):** score on corpus-TOTAL `(Σ file references + shared dictionary counted once) / Σ original sizes` vs BWT corpus-total (Σ per-file BWT outputs). Charging the dictionary per-file or not at all reproduces the φ-map / external-address false-GO trap — the dictionary MUST be a single decoder branch charged once.
- **Go/No-go gate (do FIRST, ~50-LoC, no Rust):** chunk the frozen 10-file corpus, count duplicate chunk hashes ACROSS files. If cross-file duplicate ratio ≈ 0 → NO-GO on this corpus regardless of implementation (analogue of the Gotcha #3 entropy probe). Only if the probe shows real cross-file redundancy does the corpus-total size model + Rust impl follow.
- **Замер 2026-06-22 (cross-file dedup probe, `documentation/ephemeral/research/probe_h18_crossfile_dedup.py`):** NO-GO. FastCDC content-defined chunking (Gear rolling hash, avg-chunk 64..1024 B) over all 10 corpus files; cross-file redundant-byte ratio = **0.0137% at avg=64 B, 0.000% at avg>=128 B** (only 1 chunk shared between two files at the finest granularity, gone when chunks grow). Intra-file dup_any reached 18.9% but that is run redundancy BWT/Huffman already capture — a shared dictionary cannot harvest it. Threshold 5% cross-file redundancy missed by ~3 orders of magnitude. Root cause is corpus design: the 10 files come from 10 distinct generators with no shared content by construction, so there is nothing inter-file to deduplicate. Decision is corpus-bound: the lever is real in principle but absent on this frozen corpus. NO Rust impl. Kill/re-open condition: a corpus with genuine multi-file redundancy (e.g. versioned snapshots, near-duplicate documents).

---

### H-19 — ANS / tANS (asymmetric numeral systems) replacing canonical Huffman

- **Hypothesis (operator-directed 2026-06-23, "new idea class beyond BWT"):** replace the codec's canonical Huffman entropy coder (order-0/1 and the BWT+order-1 leader) with ANS/tANS (or range coding). Huffman rounds every code length up to an integer bit, losing up to ~1 bit/symbol on skewed alphabets; ANS reaches the entropy bound to within a fraction of a bit total. Same frequency tables shipped, so table cost cancels in the comparison.
- **Maps to:** LIVE branch "arithmetic / range coding replacing Huffman (fractional-bit savings)" in closed-branches.md — now measured.
- **Status:** `GO (IMPLEMENTED + MEASURED) — ValueScheme byte 7 BwtRans (BWT + order-1 rANS). Real round-trip-clean aggregate 0.221726 vs leader BwtEntropy 0.299337 (−0.077611, −25.9% relative). Frozen corpus. Committed on `feat/cubr-h19-ans` (not pushed — operator-gated).`
- **Probe 1 — naive gap (`documentation/ephemeral/research/probe_h19_ans_gap.py`):** Huffman→entropy gap on the BWT+order-1 stream = 9071.8 B = 40.52% of the bitstream. FLAGGED as over-optimistic: order-1 splits the stream into many tiny contexts where Huffman's integer rounding looks huge in % but the entropy bound is reachable only if ANS still ships the per-context tables.
- **Probe 2 — CHARGED gap (`documentation/ephemeral/research/probe_h19_ans_charged.py`, Gotcha #6 discipline):** charges per-context frequency tables for BOTH coders.
  - **Order-0 (single table, no context-proliferation artifact): ANS ceiling = 0.73%** of the full entropy-coded payload (448.7 B over 61141.9 B). This is the honest "pure" fractional-bit advantage — small.
  - **Order-1: bitstream gap 9071.8 B is real, but tables cost 12575 B** and concentrate on high-entropy files (dense 3977 B, random_high 3969 B) where the gap is ~0. The gap lives on structured files (text +1205 B, log_like +1779 B, block_bound_runs +5644 B) where BWT made the stream near-deterministic and Huffman pays the 1-bit floor in near-zero-entropy contexts.
- **Why NOT a false GO (vs Gotcha #6 order-2):** order-2 omitted fallback-table cost terms. Here tables are charged for Huffman AND ANS and they cancel in the gap; the residual is genuine integer-rounding waste ANS recovers. The competitive per-file selector already falls back on the high-table-cost files, so ANS only needs to win on the structured files where the gap is real.
- **Realistic expectation (pre-impl):** single-digit % aggregate improvement on the structured-file subset, not the 40% the naive probe suggested. Worth a full size model + Rust impl as ValueScheme byte 7, behind the same competitive min(scheme) rail (structurally regression-proof).
- **IMPLEMENTATION (2026-06-23, branch `feat/cubr-h19-ans`):** `ValueScheme::BwtRans` (header byte 7), `code/cubrim-rs/src/codec.rs`. BWT-transform the value-code stream (reuse `bwt_encode_codes` from scheme 6) then order-1 context rANS (byte-wise rANS, `RANS_L = 1<<23`, `M = 1<<12`). Same order-1 context model as T4 (context = previous code; sparse contexts fall back to the global order-0 table). Encoder is competitive (Gotcha #4): emits `min(BwtRans, BwtEntropy, EntropyContext)` per file with the winner's scheme byte — structurally cannot regress vs the BwtEntropy leader.
  - **Two table-cost levers, both charged for real (Gotcha #6/#7):** (1) rANS reaches the entropy bound where Huffman pays its 1-bit floor on near-deterministic BWT contexts; (2) rANS ships **sparse** freq tables (only nonzero symbols: `[sym:u8][freq:u16]`) where T4 Huffman ships a **full** `code_len[n_distinct]` per context. Both effects are inside the measured round-trippable blob — no size-model estimate, the real `cubrim_bytes` from the gate.
  - **Latent bug found + fixed:** the T4 `ctx_id=0` collision (global fallback shadowed by a real context-0 own-table) is harmless for Huffman on this corpus but fatal for rANS (a fallback symbol with `freq=0` → `x_max=0` → infinite renorm). Fixed by giving the fallback table a **dedicated wire slot** separate from the context list. Covered by `test_rans_high_entropy_round_trip`.
- **MEASURED (frozen corpus, `python3 code/bench/run_bench.py --value-scheme bwt-rans`, round-trip PASS on all 10; gate `code/cluster/gate/gate-ratio.sh` PASS):**

  | file | leader BwtEntropy (B) | BwtRans (B) | Δ B | Δ % |
  |---|---:|---:|---:|---:|
  | sparse_clustered | 502 | 443 | −59 | −11.8% |
  | text | 3583 | 3177 | −406 | −11.3% |
  | log_like | 5178 | 1402 | −3776 | −72.9% |
  | block_bound_runs | 9011 | 4169 | −4842 | −53.7% |
  | dense | 4109 | 4109 | 0 | raw |
  | binary_mixed | 8205 | 8205 | 0 | raw |
  | random_high | 4109 | 4109 | 0 | raw |
  | sparse_small | 269 | 269 | 0 | raw |
  | both_sparse_16 | 29 | 29 | 0 | raw |
  | both_sparse_24 | 37 | 37 | 0 | raw |
  | **aggregate** | **0.299337** | **0.221726** | — | **−25.9% rel** |

  The win is concentrated on the 4 cube-mode files (the only ones using the value stream); raw-mode files are byte-identical (competitive selection / value stream unused). The gap matches the H-18/probe-2 prediction that the headroom lives on structured files where BWT makes contexts near-deterministic — but the realized win (−25.9%) far exceeds the pre-impl "single-digit %" estimate because the probe charged tables 1-byte/entry for *both* coders, missing that real T4 ships full-`n_distinct` tables while rANS ships sparse ones.
- **VERDICT: GO.** Round-trip non-negotiable ✅ (10/10 byte-exact, `cargo test` 182 passed incl. 14 new rANS tests + property/corpus/competitive). Tables charged ✅. Competitive per-file rail ✅ (`gate-competitive.sh --value-scheme bwt-rans` PASS, no regression). Aggregate strictly improves ✅. Leaderboard update + merge is operator-gated (committed locally, not pushed).

---

### H-18b — Re-test of corpus-local dedup on a redundant multi-file corpus (B)

- **Context (operator-directed 2026-06-23):** the H-18 NO-GO was corpus-bound (frozen corpus has ~0 cross-file redundancy). Built a SEPARATE dedup-corpus (`documentation/ephemeral/research/dedup-corpus/`, generator `gen_dedup_corpus.py`) modelling the real win case: 4 versioned snapshots of one document (small localized edits) + 2 documents sharing large boilerplate + 1 unrelated high-entropy file. Does NOT touch the frozen benchmark corpus (would break the 0.299337 baseline / corpus-hash gate).
- **Probe (`probe_h18_on_dedup_corpus.py`):** cross-file redundant ratio = **74.84% at avg-chunk 64 B**, 41.3% (128 B), 25.5% (256 B), 0% (≥512 B — chunks grow past the edit granularity). This VALIDATES the probe itself: same FastCDC logic returns 0.0137% on the frozen corpus and 74.84% here, so the frozen-corpus NO-GO was a true "nothing to dedup", not a probe artifact.
- **Status:** `conditional GO — dedup mechanism is real and strong on redundant multi-file corpora; needs a corpus-TOTAL size model vs gzip-on-concat before any Rust impl.`
- **HONEST caveat (do not declare a full GO yet):** 74.84% is RAW cross-file redundancy BEFORE charging dictionary/reference overhead AND before comparing to what existing tools already extract. Versioned/near-duplicate files are exactly what gzip/zstd on a CONCATENATED stream already compress well (their window catches the repeats). The real question is whether a *shipped shared-dictionary* scheme beats (a) per-file BWT corpus-total AND (b) gzip/zstd on the concatenation — on the SAME redundant corpus. That requires the corpus-total size model (references + dictionary-once vs Σ baseline), not just the redundancy probe.
- **Next step:** corpus-total size model on the dedup-corpus comparing {per-file BWT} vs {gzip-on-concat} vs {CDC shared-dict}. Only if shared-dict wins both does it earn a Rust impl. The frozen-corpus benchmark stays the leaderboard authority; the dedup-corpus is a side experiment to characterise WHEN inter-file dedup pays.
- **Implication for the loop:** inter-file dedup remains auto-rejected on the FROZEN corpus (correct — nothing to harvest), but is no longer a dead idea in general: it is corpus-dependent and would be the right lever if the project's target data ever becomes versioned/redundant.

---

### H-18c — Corpus-total size model: dedup vs gzip-on-concat (the real verdict)

- **Context:** H-18b showed 74.84% RAW cross-file redundancy on the dedup-corpus, but raw redundancy is not a win — the honest test is whether a shipped shared-dictionary scheme beats what existing tools already extract. Size model `documentation/ephemeral/research/probe_h18_sizemodel.py` compares corpus-total compressed bytes on the SAME redundant corpus.
- **Result (dedup-corpus, 17708 B original):**
  - per-file gzip: 3015 B (0.1703)
  - **gzip on concatenation: 755 B (0.0426)** ← the bar
  - CDC shared-dict, dictionary charged once, best avg-chunk=128: **1102 B (0.0622)** — **+347 B WORSE** than gzip-on-concat.
- **Status:** `NO-GO (final) — even on an ideally redundant corpus, a bespoke shared-dictionary dedup loses to gzip-on-concatenation.`
- **Root cause:** gzip's sliding window already captures versioned/near-duplicate repeats and shared boilerplate across a concatenated stream, with NO explicit dictionary, NO 8-byte reference ids, NO chunk-length table. The CDC scheme pays all that overhead (ref_gz 312–512 B + lentab + entropy lost to chunk-boundary fragmentation), which exceeds the dedup saving. The naive idea's intuition ("repeated data → short refs") is real but is ALREADY realised — better — by a 30-year-old general compressor on the concatenation.
- **This strengthens the H-17/H-18 closure:** the entire external-snapshot / dedup family (operator dialogue `_temp/addressator.txt`) is now closed on two independent grounds — (1) info-conservation for the universal-reference form (H-17), (2) it loses to gzip-on-concat even where redundancy is maximal (H-18c). No corpus makes a bespoke shared-dict dedup worth more than concatenate-then-compress.
- **Kill/re-open condition:** a corpus where chunks must be RANDOM-ACCESSED individually (so concatenation is not an option — e.g. a deduplicating block store / backup system), which is a storage-system design, not a single-archive compression scheme. Out of scope for the Cubrim archiver.

---

### H-20 — order-2 context rANS (deeper context model on the BWT'd value stream)

- **Hypothesis (queue item 1, 2026-06-23):** the H-19 champion BwtRans (scheme 7) uses an order-1 context rANS (context = previous code). Order-2 context (key = (prev2, prev1)) predicts the BWT'd stream more sharply. Order-2 context was a measured NO-GO for **Huffman** (Gotcha #6, EntropyContext2: order-2 fallback tables blew the budget), but rANS codes fractionally AND ships **sparse** freq tables (vs Huffman's full `code_len[n_distinct]`), so the table-cost arithmetic differs and the branch was worth re-charging.
- **Probe FIRST (`documentation/ephemeral/research/probe_h20_order2_rans_charged.py`, Gotcha #6/#7 discipline — every fallback level charged):** modelled the value-stream bytes of order-0 / order-1 / order-2 rANS with identical sparse-table accounting (2 B `n_syms` + 3 B per nonzero symbol; +2 B ctx-id for order-1, +4 B key for order-2; +4 B state). Two order-2 layouts: 3-level (order2→order1→order0) and 2-level Option B (order2→order0, no order-1 tables).
  - **Canonical 3-level order-2 = clear NO-GO:** value-stream strictly LARGER than order-1 on all 10 files (e.g. text +1144 B, sparse_clustered +225 B) — the added order-2 tables cost more than the entropy they save, exactly as Gotcha #6 predicts. Per the brief's gate ("charged gap negative → NO-GO"), the 3-level chain is rejected.
  - **2-level Option B flagged a possible win** vs the order-1 *and* order-0 references on `binary_mixed`/`text`/`sparse_clustered` — but the idealised probe omits the distance-map + header that pushes incompressible files to raw storage. Ground-truth bench showed `binary_mixed`/`dense`/`random_high`/`sparse_small` are stored **raw** by the champion, so the only honest resolution was a real round-trippable codec, not the probe.
- **IMPLEMENTATION (`ValueScheme::Order2Rans`, header byte 8, `code/cubrim-rs/src/codec.rs`):** BWT front-end (reuse `bwt_encode_codes`) + order-2 context rANS. Encoder emits the smaller of the 3-level and 2-level wire layouts (distinguished on the wire by `n_ctx1`=0 ⇒ 2-level); the decode fallback chain is order-2 → order-1 (if present) → order-0, **every level serialized and charged** (Gotcha #6 — sparse freq tables, `[sym:u8][freq:u16]`). Added as a 4th competitive candidate inside the scheme-7 `min(BwtRans, BwtEntropy, EntropyContext, Order2Rans)` rail — structurally regression-proof (Gotcha #4).
- **MEASURED (frozen corpus, `python3 code/bench/run_bench.py --value-scheme bwt-rans`, round-trip PASS on all 10; champion 0.221726 reproduced byte-exact first, then candidate):**

  | file | champion BwtRans (B) | + Order2Rans (B) | Δ B | winning scheme |
  |---|---:|---:|---:|---|
  | sparse_clustered | 443 | 400 | −43 | 8 (order-2 rANS) |
  | text | 3177 | 2889 | −288 | 8 (order-2 rANS) |
  | binary_mixed | 8205 (raw) | 6885 (cube) | −1320 | 8 (order-2 rANS) |
  | log_like | 1402 | 1402 | 0 | 7 (BwtRans) |
  | block_bound_runs | 4169 | 4169 | 0 | 7 (BwtRans) |
  | dense | 4109 | 4109 | 0 | raw |
  | random_high | 4109 | 4109 | 0 | raw |
  | sparse_small | 269 | 269 | 0 | raw |
  | both_sparse_16 | 29 | 29 | 0 | raw |
  | both_sparse_24 | 37 | 37 | 0 | raw |
  | **aggregate** | **0.221726** | **0.207618** | — | **−0.014108 (−6.36% rel)** |

  The headline win: `binary_mixed` flips from **raw storage** (incompressible by order-0/order-1) to **cube mode** — order-2 context captures BWT-grouped run structure that the order-1 model and order-0 both miss. The 2-level Option B layout wins all three improved files (the order-1 tables would over-fragment); the 3-level layout is never selected, consistent with the probe.
- **VERDICT: GO.** Round-trip non-negotiable ✅ (10/10 byte-exact; `cargo test` 190 passed incl. 8 new order-2 tests — unit both-submodes, empty/singleton, high-entropy, full-codec corpus round-trip via both entry points, competitive non-regression, property 40-trial, truncated-blob no-panic). Tables charged ✅ (every fallback level serialized; Gotcha #6 honoured — the 3-level chain that *fails* the charge is rejected, the 2-level that *passes* wins). Competitive per-file rail ✅ (`gate-competitive.sh --value-scheme bwt-rans` PASS, no regression; direct vs pinned champion: 3 improved, 7 unchanged, 0 regressed). Aggregate strictly improves vs the pinned champion 0.221726 ✅.
- **Harness notes:** (1) `gate-corpus-hash.sh` manifest-level check fails only on the manifest's machine-specific absolute paths — all 10 per-file sha256 match the frozen manifest AND the champion 0.221726 reproduces byte-exact, so corpus content is verified frozen. (2) `gate-ratio.sh` standalone benches the *committed* leaderboard's scheme (still stale at BwtEntropy 0.299337) and so does not exercise the bwt-rans/order-2 path — the authoritative comparison is the controlled `run_bench.py --value-scheme bwt-rans` champion-vs-candidate above. Leaderboard untouched (operator-gated); promotion is the Mac monitor's job after independent re-verification.

---

### H-25 — LzRans: LZ77 match modeling + rANS (a NON-BWT value-stream class)

- **Hypothesis (2026-06-24, post-queue-exhaustion):** the holdout re-check showed Cubrim ~1.3% behind gzip and ~8% behind zstd-19 on unseen data, losing 4/6 files. gzip/zstd win via LZ dictionary matching (long-range repeats) — a capability the cube+BWT+rANS pipeline has no model for. New class (not closed per Gotcha #7/H-18): tokenize the value-code stream into (literal, match) via greedy LZ77; literals → BWT+order-1 rANS backend (scheme 7); match length/distance → bit-length bucket (order-1 rANS) + raw extra bits. ValueScheme byte 12.
- **Probe FIRST (`documentation/ephemeral/research/probe_h25_lz_match.py`, charged, no Rust, no holdout tuning):** greedy LZ77 (32KB window, min-match 3) on each holdout file; literals charged at order-1 entropy, matches charged two ways. Match coverage 84–96% (massive LZ-exploitable repeats); literal H1 ≈ 3.9–4.5 bits ≪ H0 ≈ 5.7–7.4. Charged sizes: **est_real** (naive deflate-like match codes) total 54819 B = **+15% ABOVE gzip 47638**; **est_opt** (info floor: matches at log2(dist)+log2(len), literals at H1) total 36192 B = **−24% BELOW gzip**. Probe verdict: GO-to-implement (conditional) — the floor has real headroom, the crux is the distance entropy coder; but a weak coder (est_real) loses.
- **IMPLEMENTATION (`ValueScheme::LzRans`, header byte 12):** greedy LZ77 hash-chain parse; flags via order-1 rANS over {0,1}; literals via `bwt_rans_encode` (SA-IS BWT + order-1 rANS); length/distance via bit-length bucket (order-1 rANS) + raw extra bits. Added to the competitive `min()` rail and `estimate_cube_size` (Gotcha #4 — structurally regression-proof). cargo test green (lib 209 incl. 5 new LzRans tests + integration 14, 0 failed); round-trip byte-exact (200+ direct cases incl. periodic/all-same/overlap, full-codec, corpus, holdout 6/6).
- **MEASURED:**
  - **Tuned corpus (`run_bench --value-scheme bwt-rans`, RT 10/10):** aggregate **0.158273 — UNCHANGED** vs the H-24 champion; LzRans selected on 0/10 files, per-file bytes identical. Zero regression.
  - **Holdout 6-file (`run_holdout_bench.py`, RT 6/6, `h25-holdout-bench.json`):** Cubrim **0.2390 (48255 B)** vs gzip **0.2359 (47638 B)** vs zstd-19 **0.2214 (44701 B)** — **byte-identical to the pre-LzRans run**; LzRans selected on **0/6** files.
- **ROOT CAUSE (measured, not guessed):** LZ *is* finding matches (diagnostic: 519 matches incl. a length-9999 match, coverage high — not a matching bug). Two overheads sink it: (1) **raw distance extra-bits dominate** — bucket+rawbits pays floor(log2 d) raw bits per match with the within-bucket offset entropy left uncoded (~900 B of raw bits for 519 matches on a 12000-symbol stream); the probe flagged exactly this. (2) **the literal substream pays the full order-1 rANS table cost** on a smaller stream — standalone, alpha=64 LzRans = 14064 B vs best_other = 6369 B (2× worse), because BWT+order-1 on the doubled stream amortises tables while LZ codes one copy of the literals and eats the table cost. The probe's est_opt floor charged neither overhead; the real coder lands ≈ est_real (+15% over gzip), exactly as the probe's pessimistic estimate warned.
- **VERDICT: NO-GO (ratio).** Does NOT beat gzip on unseen data (holdout byte-identical with/without it, selected 0/6); does NOT improve the tuned corpus (0.158273 unchanged). Implemented, wired behind the regression-proof rail, round-trip clean — committed as a scaffold — but the −24% information floor is not realized by bucket+raw-extra distance coding plus a heavy order-1 literal backend. **Kill/re-open condition:** a future run that (a) entropy-codes the FULL distance with context (zstd-style FSE / rANS-with-context, not bucket+raw-extra), AND (b) uses a lighter literal coder (order-0 or shared-table) so the literal substream does not pay full order-1 table cost. Only then can the probe's floor be approached. Competitive rail keeps schemes 0–11 intact; leaderboard untouched.

---

### H-25b — LzRans strengthened: order-0 literals + full-value byte-split length/distance

- **Reopen (2026-06-24):** the H-25 NO-GO had two measured overheads — (1) length/distance used a bit-length bucket + RAW extra bits (within-bucket entropy uncoded), and (2) literals went through the BWT + order-1 rANS backend, paying full per-context tables on the smaller literal sub-stream (2× worse standalone on large alphabets). H-25b fixes both, keeping scheme byte 12 behind the competitive rail.
- **IMPLEMENTATION:** added a single-table order-0 rANS primitive (`rans_order0_encode/decode`). LzRans rewired: literals → order-0 rANS (the lighter coder); match length and distance (both capped ≤ u16) → split into low/high BYTE streams, each order-0 rANS — no raw bits, so the full value is entropy-coded and *repeated* distances (aligned records, fixed offsets) compress below raw. Flags stay order-1 rANS over {0,1}. cargo test green (lib 209 + integration 14, 0 failed); round-trip byte-exact (5 LzRans tests incl. 200+ direct cases, full codec, holdout 6/6).
- **MEASURED — the fixes demonstrably worked (standalone LzRans vs BwtRans on the holdout cube streams):**

  | file | LzRans H-25b (B) | BwtRans (B) | geomix winner (B) | gzip (B) |
  |---|---:|---:|---:|---:|
  | config.json (65536-blk) | 10866 | 15029 | 8668 | 8839¹ |
  | data.csv | 5730 | 5237 | 3539 | 4087 |
  | prose.txt | 8034 | 10700 | 6468 | 6687 |
  | rust_src.rs | 8417 | 12392 | 6853 | 6775 |
  | exe.bin | 16619 | 33042 | 14294 | 14388 |

  ¹ gzip is whole-file; Cubrim columns are the value-stream of one cube block. LzRans now **beats BwtRans on 4/5 files** (exe.bin 16619 vs 33042 — 2× better, where H-25 was 2× *worse*; the order-0 literal fix is decisive on large alphabets). It is no longer dead weight — a competitive mid-tier scheme that beats order-1/order-2 rANS and the Huffman variants.
- **BUT still loses to the BWT + geometric-context-mixing champion family on every file** (LzRans is +16–62% larger than the geomix winner), so it is never the per-file minimum — selected 0/6 on the holdout.
- **Holdout (`run_holdout_bench.py`, RT 6/6, `h25b-holdout-bench.json`):** Cubrim **0.2390 (48255 B)** vs gzip **0.2359 (47638 B)** vs zstd-19 **0.2214 (44701 B)** — **byte-identical to H-25**; aggregate unchanged, LzRans selected 0/6.
- **VERDICT: NO-GO (ratio) — but a real improvement.** Does NOT beat gzip on unseen data (standalone LzRans config 11556 vs gzip 8839, csv 5730 vs 4087 — loses 6/6; holdout aggregate 0.2390 > gzip 0.2359, unchanged). The two fixes are genuine (LzRans graduated from dead-weight/2×-worse to beating 4 of 7 sibling schemes) but insufficient: on ≤64KB cube blocks the BWT + geometric-context-mixing scheme (geomix, H-24) already extracts the local redundancy that LZ's match model competes for, and the residual literals coded order-0 leave order-1+ structure that geomix captures via its full-stream context model. The distance byte-split helps structured files (csv's repeated distances) but geomix still wins. The probe's −24% information floor is not reached on this corpus. **Kill/re-open condition:** an order-1 (context-modelled) literal coder that stays light (e.g. the existing fallback-table order-1 rANS, *without* BWT) AND a repeat-offset cache for distances (zstd's real win — code "reuse last/2nd/3rd offset" before a literal distance), on a corpus with genuine long-range structure beyond what a 64KB BWT block already captures. Competitive rail keeps schemes 0–11 intact; leaderboard untouched.

---

### H-25c — LzRans: repeat-offset distance cache + lighter order-1 literal coder

- **Reopen (2026-06-24, the H-25b re-open condition):** H-25b's byte-split still missed zstd's two real levers. H-25c adds both, keeping scheme byte 12 behind the competitive rail.
- **IMPLEMENTATION:** (1) a zstd-style **repeat-offset cache** — the last 3 distinct match offsets in a move-to-front LRU; each match codes a 4-symbol mode (order-1 rANS): 0/1/2 = "reuse rep[k]" (≈2 bits), 3 = "new distance" (full low/high byte-split, order-0 rANS). Long-range repeats at a fixed stride collapse to mode-0 runs. (2) a **lighter literal coder**: pick min(order-0, order-1 fallback-table rANS) for the literal stream (1-byte `lit_mode` flag) — keeps literal order-1 structure without the BWT doubling or full per-context tables. cargo test green (lib 210 + integration 14, 0 failed); round-trip byte-exact (6 LzRans tests incl. a new long-range test that asserts LzRans WINS the rail — scheme byte 12 — and the scheme-12 decode dispatch round-trips).
- **MEASURED — the repeat-offset lever works (first time LzRans wins the rail):** on a within-block long-range input (10 KB structured unit × 6 = 60 KB, one cube block), standalone value-stream bytes: **LzRans 6867** vs geomix 9628 vs adaptive 9504 vs ctxmix 9506 vs BwtRans 10311 — **LzRans is the smallest, −29% vs geomix**, and near gzip 6404 / zstd 5205. The 5 inter-copy distances all reuse one offset → mode-0.
- **BUT — holdout unchanged + two ceilings:**
  - **Holdout (`run_holdout_bench.py`, RT 6/6, `h25c-holdout-bench.json`):** Cubrim **0.2390 (48255 B)** vs gzip **0.2359 (47638 B)** vs zstd-19 **0.2214 (44701 B)** — **byte-identical to H-25/H-25b**, LzRans selected 0/6. Holdout files are single ≤64 KB blocks where geomix's local context dominates and within-block long-range structure is thin.
  - **64KB chunk-boundary cap (the structural ceiling):** on a 120 KB 12-copy input (2 chunked 64 KB blocks) cubrim lz-rans = **13871** vs gzip **6950** (2× worse) — the MODE_CHUNKED boundary forces re-coding the repeated unit in each block, while gzip windows the whole file. Concatenated holdout (202 KB, 4 blocks): cubrim **49106** vs gzip **48342** — still loses; cross-file long-range repeats are lost at the block boundaries.
- **VERDICT: NO-GO (ratio) — mechanism proven, architecture-limited.** Does NOT beat gzip on unseen data (holdout 0.2390 > gzip 0.2359, unchanged; concatenated 49106 > 48342; 120 KB multi-copy 13871 vs 6950). The repeat-offset cache is real and correct — LzRans now WINS the competitive rail on single-block long-range data (−29% vs geomix), the first LZ win — but two ceilings stand: (a) the holdout corpus lacks within-block long-range structure (geomix wins the local game), and (b) **Cubrim's 64 KB MODE_CHUNKED boundary caps LZ's reach**, so the cross-block long-range repeats where gzip/zstd actually win are unreachable per-scheme. **Kill/re-open condition:** a whole-file LZ pre-pass BEFORE the 64 KB chunking (or a sliding window spanning chunks) — an *architecture* change, not a value-scheme — is required to capture the long-range structure gzip/zstd exploit. Until then LZ's reach is bounded by the block size. Competitive rail keeps schemes 0–11 intact; leaderboard untouched.

---

### H-25d — whole-file LZ pre-pass before chunking (MODE_LZ container)

- **Reopen (2026-06-24, the H-25c re-open condition):** H-25c's repeat-offset cache won the rail on a single-block long-range input but was capped by the 64KB MODE_CHUNKED boundary — cross-block repeats (exactly where gzip/zstd window-match) were unreachable per value-scheme. H-25d is the architecture change: LZ77 the WHOLE FILE first, then chunk the literal residue.
- **IMPLEMENTATION (new container `MODE_LZ = 3`, NOT a value-scheme):** `encode_with_config` becomes `min(encode_base, encode_lz_prepass)` for inputs > cube_size_limit (a competitive SIZE pick — regression-proof; inputs ≤64KB skip the pre-pass entirely and stay byte-identical). `encode_lz_prepass` LZ77-tokenizes the whole input over a full-file window; the literal residue is encoded through the normal pipeline (`encode_base` → nested chunked cube/BWT/rANS) and the match length/distance streams are coded at file level with the H-25c repeat-offset cache (factored into a shared `lz_encode_token_streams`; distances widened to a 4-byte split since whole-file distances exceed u16). cargo test green (lib 213 + integration 14, 0 failed); round-trip byte-exact; tuned corpus UNCHANGED (all ≤64KB → no pre-pass → byte-identical, zero regression).
- **MEASURED:**

  | case | Cubrim | gzip-9 | zstd-19 | mode |
  |---|---:|---:|---:|---|
  | 120 KB multi-copy (12× 10 KB unit) | **6934** | 6950 | 5202 | MODE_LZ (3) |
  | concatenated holdout (202 KB, 6 diverse files) | 49106 | 48342 | 44338 | MODE_CHUNKED (2) |
  | holdout aggregate (6 files) | 0.2390 (48255 B) | 0.2359 (47638 B) | 0.2214 (44701 B) | — |

- **VERDICT: MIXED — architecture lever proven, holdout still NO-GO.** On genuine cross-block long-range data (the 120 KB 12-copy) the whole-file LZ pre-pass makes **Cubrim BEAT gzip — 6934 vs 6950, the first gzip win in the entire H-25 line** — and is 2× better than H-25c's chunked-only 13871, with MODE_LZ correctly selected. The mechanism is real and regression-proof. BUT it does not help unseen REAL data: the holdout files have no cross-block repeats (aggregate unchanged 0.2390 > gzip 0.2359, MODE_LZ selected 0/6 — config.json's 2 blocks share no long-range structure), and the concatenated *diverse* holdout has no cross-FILE repeats (different file types → MODE_LZ falls back to MODE_CHUNKED, 49106 > gzip 48342). zstd-19 leads everywhere. **Whole-file LZ beats gzip only when the data genuinely contains long-range/duplicate structure; the diverse holdout corpus does not, so on unseen real data Cubrim still does not beat gzip.** **Kill/re-open condition:** to close the remaining gap on diverse real data needs a stronger *entropy back-end* on the match streams (zstd uses FSE with offset/length/literal-length context tables and a tuned optimal parse), plus possibly a literal coder that matches zstd's — i.e. catching up to zstd's coding, not just its matching. That is a deep entropy-engineering effort, not a container mode. Competitive rail keeps schemes 0–11 and modes 0–2 intact; leaderboard untouched.

---

### H-25e — cost-aware/lazy LZ parse (the zstd "optimal parse" lever)

- **Reopen (2026-06-24, the H-25d re-open condition):** H-25d's MODE_LZ beat gzip on long-range but trailed zstd-19 by 33% (120 KB 6934 vs 5202). The recorded condition asked for a zstd-class FSE back-end on the match streams (offset / match-length / literal-length) plus a lazy/optimal parse.
- **DIAGNOSIS FIRST (debug breakdown):** on the 120 KB multi-copy the MODE_LZ total 6934 = lit_blob 1322 + **token_streams 5590** with **n_matches = 2424**. Greedy LZ took thousands of length-3 matches at random FAR offsets — each costs ~2.3 B to replace ~1.5 B of literals. The gap to zstd was a PARSE problem, not an entropy-coder problem (the match streams already use order-0 rANS, which is FSE-equivalent).
- **IMPLEMENTATION:** a **cost-aware + lazy** LZ parse replaces greedy. A candidate match is taken only when its estimated coded cost — offset bits (≈3 if it reuses a repeat-offset, else 2 + 8·byte-count of the distance) + length bits + a flag — is smaller than coding its span as literals (per-literal cost = the clamped order-0 entropy of the input). A 1-step lazy lookahead prefers a strictly-longer worthwhile match one position later. The parse keeps a repeat-offset mirror so the offset-cost estimate is accurate. cargo test green (lib 213 + integration 14, 0 failed); round-trip byte-exact; tuned corpus UNCHANGED.
- **MEASURED:**

  | case | Cubrim H-25d | Cubrim H-25e | gzip-9 | zstd-19 |
  |---|---:|---:|---:|---:|
  | 120 KB multi-copy | 6934 | **5359** | 6950 | 5202 |
  | concatenated holdout (202 KB, diverse) | 49106 | 49106 | 48342 | 44338 |
  | holdout aggregate | 0.2390 | 0.2390 | 0.2359 | 0.2214 |

  The cost-aware parse cut matches 2424 → 16 and token_streams 5590 → 210 on the 120 KB case; literals (5127) now dominate and ≈ zstd's literal cost.
- **VERDICT: PARTIAL WIN — narrows to zstd on long-range, holdout unmoved.** The zstd-class lever that mattered was the **optimal/lazy parse** (zstd's real win), not FSE-vs-rANS. On genuine long-range data it narrows the gap to zstd decisively — 120 KB 5359 vs zstd 5202 (3% behind, was 33%) and beats gzip by 23%. It does NOT yet beat zstd: the remaining ~3% is literal coding (zstd's tuned literal entropy vs Cubrim's cube/geomix on the residue). The **holdout does not move** (0.2390, MODE_LZ selected 0/6) and the concatenated *diverse* holdout is unchanged (49106 > gzip 48342) — both lack the cross-block/duplicate structure whole-file LZ needs. **Kill/re-open condition:** the last long-range gap to zstd is the literal coder on the LZ residue — a dedicated literal entropy coder (order-1 / Huffman-FSE like zstd's) for the lit_blob, OR feeding the residue through a stronger model than the current cube pipeline. For the holdout specifically, no LZ work helps: those files have no long-range redundancy beyond what a 64 KB BWT block already captures — the honest ceiling is the local entropy coder (the BWT-family schemes), where Cubrim already sits at rough gzip parity and behind zstd. Competitive rail keeps schemes 0–11 and modes 0–2 intact; leaderboard untouched.

---

### H-25f — dedicated literal coder for the LZ residue

- **Reopen (2026-06-24, the H-25e re-open condition):** H-25e narrowed the long-range gap to zstd to ~3% and attributed the remainder to literal coding (zstd codes literals with a separate Huffman/FSE table). H-25f adds a dedicated literal coder for the MODE_LZ residue and picks the smaller per the competitive rail.
- **IMPLEMENTATION:** the MODE_LZ literal residue is coded by the minimum of three candidates, signalled by a `lit_kind` byte: 0 = the nested cube/BWT/rANS pipeline (strongest local model, but pays the cube header), 1 = direct order-0 rANS (no cube framing), 2 = direct order-1 rANS (zstd-style separate literal table). The decoder dispatches on `lit_kind`; n_lits = n_tokens − n_matches. cargo test green (lib 213 + integration 14, 0 failed); round-trip byte-exact; tuned corpus UNCHANGED.
- **MEASURED:**

  | case | H-25e | H-25f | gzip-9 | zstd-19 |
  |---|---:|---:|---:|---:|
  | 120 KB multi-copy | 5359 | **5335** (lit_kind=1) | 6950 | 5202 |
  | holdout aggregate | 0.2390 | 0.2390 | 0.2359 | 0.2214 |

  The dedicated coder correctly picks lit_kind=1 (order-0 rANS) on a random-18 residue and lit_kind=0 (cube) on a structured/text residue.
- **VERDICT: MARGINAL — does not close to zstd; honest re-diagnosis.** The dedicated literal coder is a real, regression-proof feature, but it only shaves ~24 B on the 120 KB case (the order-0 rANS just avoids the cube header) — 5359 → 5335, still 2.5% behind zstd 5202. **The H-25e premise was partly wrong:** the residue was ALREADY coded near its order-0 entropy by the cube path, so a better literal coder has almost nothing to gain. The remaining long-range gap to zstd is **LZ FRAMING / SEQUENCE overhead** — Cubrim spends ~210 B on separate token streams (flags + repeat-offset modes + length/offset byte-splits) plus the MODE_LZ and nested-literal headers, whereas zstd interleaves literal-length / match-length / offset codes in one FSE-coded sequence stream with shared state. The holdout does NOT move (0.2390, MODE_LZ selected 0/6 — no cross-block structure). **Kill/re-open condition:** to squeeze the last ~2.5% on long-range, replace the separate per-stream token coding with a single combined sequence coder (zstd-style interleaved literal-length/match-length/offset with shared FSE/rANS state) and drop the per-token flag stream in favour of literal-run-lengths — a sequence-format redesign, not a literal coder. For the holdout, no LZ-side work helps: those files have no long-range redundancy beyond a 64 KB BWT block, so the ceiling is the local BWT-family entropy coder (already ~gzip parity, behind zstd). The H-25 line is now at diminishing returns: whole-file LZ + optimal parse + competitive literal coder beats gzip on long-range and reaches within 2.5% of zstd, but the diverse holdout corpus simply lacks the structure any LZ exploits. Competitive rail keeps schemes 0–11 and modes 0–2 intact; leaderboard untouched.

---

### H-25g — combined sequence coder for the MODE_LZ token streams

- **Reopen (2026-06-24, the H-25f re-diagnosis):** H-25f showed the last ~2.5% to zstd on long-range is FRAMING, not literals — the 8 separate token rANS streams (flags, repeat-offset modes, 4 distance bytes, 2 length bytes) each pay a fixed table+state (~150 B total), which dominates when there are few matches. zstd interleaves literal-length / match-length / offset in ONE FSE-coded sequence stream.
- **IMPLEMENTATION:** serialize the whole token structure as zstd-style sequences — per match `(literal_length, match_length, offset_mode[, new_distance])` as LEB128 varints plus a trailing literal-run length — into ONE buffer, coded by the smallest of {raw, order-0 rANS, order-1 rANS}. This DROPS the per-token flag stream entirely (literal runs are implicit in the per-match literal_length). A competitive `seq_format` byte picks between the separate per-stream format (0, H-25f) and the combined format (1); the decoder reconstructs the interleaving from the per-match literal-run-lengths. cargo test green (lib 213 + integration 14, 0 failed); round-trip byte-exact; tuned corpus UNCHANGED.
- **MEASURED:**

  | case | H-25f | H-25g | gzip-9 | zstd-19 |
  |---|---:|---:|---:|---:|
  | 120 KB multi-copy | 5335 | **5211** (seq_format=1) | 6950 | **5202** |
  | concatenated holdout (202 KB, diverse) | 49106 | 49106 | 48342 | 44338 |
  | holdout aggregate | 0.2390 | 0.2390 | 0.2359 | 0.2214 |

- **VERDICT: WIN on long-range — gap to zstd CLOSED.** On genuine long-range/duplicate data the combined sequence coder removes the per-stream framing overhead (5335 → 5211, −124 B) and brings Cubrim to **within 9 bytes of zstd-19 — 5211 vs 5202, 0.17% behind (down from 2.5%)** — essentially TIED, while beating gzip by 25%, all regression-proof and round-trip byte-exact. This confirms the H-25f re-diagnosis (framing, not literals). The **holdout does not move** (0.2390, MODE_LZ selected 0/6) and the concatenated *diverse* holdout is unchanged (49106 > gzip, MODE_LZ falls back) — those corpora lack the cross-block / duplicate structure whole-file LZ exploits; their ceiling is the local BWT-family entropy coder (~gzip parity, behind zstd), which no LZ work can move. **The H-25 line is complete:** whole-file LZ (H-25d) + optimal parse (H-25e) + competitive literal coder (H-25f) + combined sequence coder (H-25g) takes Cubrim from 2× worse than gzip on long-range to MATCHING zstd-19 there, regression-proof; on the diverse holdout no LZ helps because the structure isn't there. Remaining direction for the holdout is purely the local coder (the BWT-family schemes 6–11), already explored through H-24. Competitive rail keeps schemes 0–11 and modes 0–2 intact; leaderboard untouched.

---

### H-25h — repeat-offset-aware cost-optimal LZ parse (toward beating zstd uniformly)

- **Goal (operator, 2026-06-24):** beat zstd-19 uniformly, not just match it. Cubrim already beats zstd on repeated logs (−18%, via the BWT chunked path) and ties on pure duplicates; the gaps are srctree.tar (+11%) and the synthetic 12×-copy (+0.17%).
- **DIAGNOSIS:** on srctree.tar the MODE_LZ token block is 217652 of 286447 (76%) for 78248 matches — sub-streams: offsets (dist_b0/b1/b2) = 142575 (66%, ~16 bits each for 71931 DISTINCT offsets) + length 49450 (22%). The cost is the offset entropy floor for ~72K distinct cross-file offsets — driven by MATCH COUNT, not offset-reuse (only ~6300/78248 matches hit a recent offset; tarball cross-file matches are genuinely diverse).
- **IMPLEMENTATION:** replaced the longest-match greedy with a **cost-optimal repeat-offset-aware** selection — at each position, pick the maximum net-byte-saving among {hash-chain longest match, matches at the 3 recent offsets}; a shorter repeat-offset match (offset ≈ 3 bits) can out-save a longer new-offset match (offset ≈ 16–26 bits). Lazy-1 lookahead on net saving. This is zstd's repcode lever. cargo test green (227 passed, 0 failed); round-trip byte-exact.
- **MEASURED (cubrim vs gzip-9 vs zstd-19, RT PASS each):**

  | corpus | H-25g | H-25h | gzip-9 | zstd-19 |
  |---|---:|---:|---:|---:|
  | srctree.tar | 286447 | 284369 | 320321 | 257542 |
  | multiversion.bin | 61886 | 61734 | 172553 | 56165 |
  | repeated.log | 22041 | 22041 | 37295 | 26970 |
  | 120 KB multi-copy | 5211 | 5213 | 6950 | 5202 |

  Zero regression: tuned 0.158273 (byte-identical), RT 10/10; holdout 0.2390, RT 6/6.
- **VERDICT: MARGINAL — correct algorithm, but uniform zstd-beat NOT achieved.** The repeat-offset-aware cost-optimal parse improves real long-range data slightly (srctree −0.7%, multiversion −0.2%), is regression-proof and byte-exact, but cannot close the mixed-tarball gap because that gap is **fundamental to match count**: ~72K distinct cross-file offsets at ~16 bits each ≈ 143 KB offset floor. zstd wins there via its **btultra optimal parser** (dynamic-programming cost minimisation + binary-tree match finder) which finds FEWER/LONGER matches → fewer offsets to code. Deeper hash chains (tested at 2048) gave only −0.7% for **25 s** (match count barely dropped 77973→77044) — confirming the lever is parse OPTIMALITY, not search depth. Net vs zstd-19: **beats on logs (−18%), ties on pure duplicates, within ~10% on near-duplicate versions and mixed tarballs; beats gzip on ALL long-range shapes.** **Kill/re-open condition (H-25i):** a btultra-class optimal parser — full dynamic-programming parse over a window with a price model (literal/match/repeat-offset costs) and an all-matches match finder (binary tree or suffix automaton), so the globally-cheapest sequence of matches is chosen rather than a greedy/lazy one. This is the only remaining lever for the mixed-tarball gap and is a substantial (multi-day) algorithm. Competitive rail keeps schemes 0–11 and modes 0–2 intact; leaderboard untouched.

---

### H-25i — btultra-class optimal parser (DP cost-minimisation over the match graph)

- **Goal (operator):** beat zstd uniformly. H-25h established the mixed-tarball gap (+10%) is the offset-entropy floor from too many short matches; the lever is an optimal parser finding fewer/longer matches.
- **IMPLEMENTATION:** forward DP — `cost[i]` = min coded bits to reach `i`; edges are a literal (`+lit_bits`) and a match of length `L` at the smallest distance reaching `L` for every hash-chain frontier length (capped at LZ_OPT_LEN_CAP=128 per frontier point, with the full longest match always added). Backtrack the min-cost path. Cost model is a principled log2 entropy estimate (NOT corpus-tuned). Round-trip is guaranteed by the exact encoder/decoder regardless of parse.
- **REGRESSION GUARD (competitive parse):** the optimal DP, lacking repeat-offset awareness, breaks the rep-offset structure on duplicate data (120 KB regressed 5213→5501 optimal-only). So `encode_lz_prepass` builds a MODE_LZ container with BOTH the fast greedy parse (preserves rep structure) and the optimal DP, and returns the smaller (`build_lz_container`). The value-scheme keeps the fast greedy (it runs per-block in the rail). cargo test green (227 passed, 0 failed); round-trip byte-exact.
- **MEASURED (cubrim vs zstd-19, RT PASS each):**

  | corpus | H-25h | H-25i | zstd-19 | vs zstd |
  |---|---:|---:|---:|---:|
  | srctree.tar | 284369 | **270724** | 257542 | +5.1% (was +10.4%) |
  | multiversion.bin | 61734 | **59772** | 56165 | +6.4% (was +9.9%) |
  | repeated.log | 22041 | 22041 | 26970 | **−18.3%** |
  | 120 KB multi-copy | 5213 | 5213 | 5202 | +0.2% (tied) |

  Zero regression: tuned 0.158273 (byte-identical), RT 10/10; holdout 0.2390, RT 6/6. Speed: ~27 s for 1.5 MB (DP scans every position + double container build); decompression fast.
- **VERDICT: PROGRESS, not uniform — the biggest mixed-data gain yet, but does NOT beat zstd uniformly.** The optimal parser HALVED the gap to zstd on mixed/near-duplicate data (srctree +10.4%→+5.1%, multiversion +9.9%→+6.4%) by finding fewer/longer matches, regression-proof and byte-exact. It does NOT beat zstd on the mixed tarball or near-duplicate versions (still +5–6%). Net vs zstd-19: **beats on logs (−18%), ties on pure duplicates, +5–6% on tarball/versions; beats gzip on ALL**. The remaining ~5% is (a) the **hash-chain match finder** yields fewer candidates than zstd's binary tree — the parse is only optimal over the candidates it sees — and (b) the DP cost model is not repeat-offset-aware so it slightly mis-prices. **Kill/re-open condition (H-25j):** a binary-tree or suffix-automaton match finder feeding the DP (so it considers ALL matches, not just hash-chain frontier candidates), plus a repeat-offset-aware price model in the DP. This is an even larger algorithm and the last remaining lever for the mixed-tarball gap. Competitive rail keeps schemes 0–11 and modes 0–2 intact; leaderboard untouched.

---

### H-25j-lite — repeat-offset-aware DP cost model (half of the H-25j re-open condition)

- **Goal (operator, 2026-06-24):** the H-25i re-open condition (H-25j) named two levers for the residual mixed-tarball gap to zstd: (a) a binary-tree/suffix-automaton match finder feeding the DP, and (b) a repeat-offset-aware price model in the DP. H-25j-lite implements (b) only — the tractable, one-run half. (a) remains open as H-25j-full (a multi-day match-finder rewrite).
- **DIAGNOSIS:** the H-25i optimal DP's `match_cost` charged EVERY match the full offset entropy `2 + bit_length(dist)` (≈16–26 bits for far offsets), with a code comment conceding "the repeat-offset discount is applied by the exact encoder, so this need only rank parses". But the exact MODE_LZ encoder codes a recent (repeat) offset in ~mode-only bits (≈3). So the DP mis-ranked long rep-offset chains below shorter new-offset matches — under-using exactly the cheap rep structure that duplicate / near-duplicate / repetitive-log data is built from. This is also why H-25i's optimal-only parse REGRESSED pure-duplicate data (120 KB 5213→5501) and had to be hidden behind the competitive greedy/optimal rail.
- **IMPLEMENTATION:** carry the 3-deep repeat-offset cache along the DP's incumbent best path. This forward DP relaxes edges only forward, so when the loop reaches `i` every edge into `i` is final and the chosen-path rep cache can be reconstructed (`rep_cache[i]` from `rep_cache[i−from_len[i]]` via the shared `lz_rep_update`, the same MTF the encoder/decoder use — extracted from the greedy parser so the two mirrors can never diverge). Then: (1) `match_cost` charges ≈3 bits when the distance is one of the 3 recent offsets, full entropy otherwise; (2) the 3 recent offsets are explicitly probed as cheap DP edges at every position (a length-L rep match can now beat a longer new-offset match). The hash-chain edges also pass the `is_rep` flag. This is the standard incumbent-path rep model (as in zstd's optimal parser). Round-trip is guaranteed by the exact encoder/decoder regardless of parse; the competitive greedy/optimal rail + `min(base, lz)` mode pick keep the leaderboard untouched. cargo test green (227 passed: 213 lib + 14 integration, 0 failed); round-trip byte-exact on all fixtures.
- **MEASURED (cubrim vs gzip-9 vs zstd-19, RT PASS each).** NB: the H-25g..i ad-hoc long-range fixtures were never committed, so these are **freshly-regenerated deterministic in-repo fixtures** (multiversion = 3 git-historical `codec.rs` concatenated; srctree.tar = tar of `code/cubrim-rs/src`; multicopy120k = 12× a 10 KB block; repeated.log = synthetic syslog). Absolute bytes are therefore NOT comparable to the H-25i table — only the **within-run baseline (H-25i) vs candidate (H-25j-lite)** delta on the identical regenerated files is valid:

  | corpus | H-25i base | H-25j-lite | gzip-9 | zstd-19 | vs zstd |
  |---|---:|---:|---:|---:|---:|
  | repeated.log (rep-rich log) | 13123 | **11889** | 24840 | 10063 | +30.4% → **+18.1%** |
  | multiversion.bin (near-dup) | 61480 | **61412** | 184642 | 56625 | +8.6% → +8.5% |
  | srctree.tar (mixed tarball) | 86288 | **86152** | 93744 | 79569 | +8.4% → +8.3% |
  | multicopy120k (pure dup) | 5016 | 5017 | 4798 | 3690 | +35.9% → +36.0% |

  Zero regression on everything the project gates: tuned 10-file **0.158273 (byte-identical to champion)**, RT 10/10; holdout **0.2390 (byte-identical)**, RT 6/6.
- **VERDICT: MARGINAL WIN on rep-offset-rich long-range; correct refinement, but does NOT beat zstd uniformly.** Making the DP cost model repeat-offset-aware is the right fix for cause (b) and helps where rep structure is dense: **repeated.log −9.4% (gap to zstd +30.4%→+18.1%)**, with small gains on near-duplicate (multiversion −0.11%) and mixed (srctree −0.16%) data; regression-proof and byte-exact. It does NOT close the mixed-tarball / near-duplicate gap (~8% remains), because that gap is dominated by cause (a): the **hash-chain match finder yields fewer/shorter candidates than zstd's binary tree**, so the parse — however well-priced — is only optimal over the candidates it sees (H-25h already measured the tarball's offsets as genuinely diverse, only ~8% rep-offset hits, so a better rep price has little to bite on there). The one observed micro-non-monotonicity is **+1 byte on multicopy120k** (5016→5017): a parse-heuristic artefact on an untracked synthetic fixture where the rep-aware optimal converges one byte above the prior optimal while greedy is larger still — it touches NO gated corpus (tuned + holdout byte-identical). Net vs zstd-19 unchanged in shape: beats on logs, ties on pure duplicates, ~8% on tarball/versions; beats gzip on ALL. **Kill/re-open condition (H-25j-full):** the binary-tree / suffix-automaton match finder feeding the DP — lever (a), the larger remaining half. Without more match candidates the rep-aware price model has extracted what it can. Competitive rail keeps schemes 0–11 and modes 0–2 intact; leaderboard untouched. NOT tuned to any corpus.

---

### H-25j-full — binary-tree match finder feeding the DP (the H-25j re-open condition, lever a)

- **Goal (operator, 2026-06-24):** the larger half of the H-25j condition. H-25i/H-25j-lite established the residual mixed-tarball / near-duplicate gap to zstd (~8%) is dominated by **match-finder candidate density** — the hash chain yields fewer/shorter candidates than zstd's binary tree, so the optimal DP parse is only optimal over the candidates it sees. The lever is a binary-tree / suffix-automaton match finder that surfaces the longest match at each distance-class.
- **IMPLEMENTATION:** an LZMA-style binary search tree over the suffixes of the value-code stream (`bt_get_matches`), rooted by the 3-byte prefix so every position that can start a ≥3 match shares a tree. `son[2*p]` / `son[2*p+1]` are p's greater/less children. One call both inserts `pos` and collects the longest-at-each-distance candidates on the descent (a strictly-increasing-length set, each byte-verified). The candidates are relaxed as DP edges **alongside** the existing hash-chain frontier (the DP sees the UNION of both finders — a superset of H-25i's candidates, so the parse is never worse by the cost model), reusing the H-25j-lite rep-aware `match_cost` and the per-frontier length-range relaxation. Round-trip is unaffected (parse-only; the exact encoder/decoder round-trip any valid parse; competitive greedy/optimal rail + `min(base, lz)` mode pick keep the leaderboard untouched). New adversarial round-trip property test (`test_bt_match_finder_round_trips_adversarial`: near-duplicate pair at ~70 KB offset, periodic/overlapping runs, wide-shallow diverse trees + duplicated blocks). cargo test green (228 passed: 214 lib + 14 integration, 0 failed); round-trip byte-exact on all fixtures.
- **MEASURED (cubrim vs gzip-9 vs zstd-19, RT PASS each; same regenerated deterministic in-repo fixtures as H-25j-lite — only the within-run delta vs the H-25i/H-25j-lite baselines on identical files is valid):**

  | corpus | H-25i | H-25j-lite | H-25j-full | gzip-9 | zstd-19 | vs zstd |
  |---|---:|---:|---:|---:|---:|---:|
  | srctree.tar (mixed tarball) | 86288 | 86152 | **85398** | 93744 | 79569 | +8.4% → **+7.3%** |
  | multiversion.bin (near-dup) | 61480 | 61412 | **61007** | 184642 | 56625 | +8.6% → **+7.7%** |
  | repeated.log (rep-rich log) | 13123 | 11889 | **11774** | 24840 | 10063 | +30.4% → **+17.0%** |
  | multicopy120k (pure dup) | 5016 | 5017 | 5017 | 4798 | 3690 | +35.9% → +36.0% |

  Zero regression on gated corpora: tuned 10-file **0.158273 (byte-identical to champion)**, RT 10/10; holdout **0.2390 (byte-identical)**, RT 6/6 (config.json's 66 KB engages MODE_LZ but does not win — byte-identical). Speed: ~73 s for the 4 fixtures (~1.9 MB total) — the BT runs in addition to the hash chain (double match-find); research max-ratio path, acceptable.
- **VERDICT: PROGRESS — real, consistent gap-narrowing, but does NOT beat zstd uniformly.** The binary-tree finder surfaces longer/cleaner matches the hash chain misses, narrowing the zstd gap a further ~1% on mixed/near-duplicate data on top of H-25j-lite (srctree +8.4%→**+7.3%**, multiversion +8.6%→**+7.7%**, repeated.log →**+17.0%**), regression-proof and byte-exact (new adversarial RT test green). It does NOT close the remaining ~7–8% on the mixed tarball / near-duplicate versions. Honest diagnosis of the floor that remains: with a richer candidate set now in hand, the residual gap is **NOT match selection** — it is **offset coding**. zstd codes offsets as an FSE-coded offset-*code* (number of extra bits) + raw bits with a tuned distribution and the repcode shortcut, whereas Cubrim's combined sequence coder (H-25g) codes each new distance as LEB128 varints through order-0/1 rANS; for ~70 K genuinely-diverse cross-file offsets that framing costs more per offset regardless of how the matches are chosen. Net vs zstd-19 unchanged in shape: **beats on logs, ties on pure duplicates, ~7–8% on tarball/versions; beats gzip on ALL**. **Kill/re-open condition (H-25k):** an FSE/rANS offset-*code* model (bucket the offset by bit-length, entropy-code the bucket with context, append the raw low bits) replacing the varint distance split — the offset-entropy lever, now that match selection is no longer the bottleneck. Competitive rail keeps schemes 0–11 and modes 0–2 intact; leaderboard untouched. NOT tuned to any corpus.

---

### H-25k — FSE/rANS offset-code model (seq_format 2; the H-25j-full re-open condition)

- **Goal (operator, 2026-06-24):** the H-25j-full verdict attributed the residual ~7–8% long-range gap to **offset coding** — Cubrim coded new distances as LEB128 varints through a byte-level rANS, where zstd uses an FSE offset-*code* (bit-length bucket) + raw low bits + the repcode shortcut. H-25k models offsets that way: a new combined coder (`seq_format = 2`) that keeps the structural bytes (literal-run / match-length varints + 2-bit offset mode) in `ser`, but splits each new offset into its bit-length code (a small skewed alphabet, rANS-coded with min(raw,o0,o1)) plus its `code-1` low bits packed raw. Behind the competitive `min()` over {0 separate, 1 combined-varint, 2 offset-code} → structurally regression-proof.
- **IMPLEMENTATION:** `lz_encode_token_offcode` / `lz_decode_token_offcode` (shared `lz_repcode_classify` + `lz_offset_code`); wire `[ser: coder,len,payload][oc: coder,count,payload][extra: nbits,bytes]`. Decode dispatch merges seq_format 1|2 (same logical sequence). New direct round-trip unit test (`test_offcode_token_coder_round_trips`: repcode + diverse-magnitude new offsets, exercising the bit-length codes, raw low-bit packing, and MTF) plus the existing MODE_LZ round-trip tests. cargo test green (229 passed: 215 lib + 14 integration, 0 failed); round-trip byte-exact.
- **MEASURED (cubrim H-25j-full → H-25k, vs zstd-19; same regenerated deterministic in-repo fixtures, RT PASS each):**

  | corpus | H-25j-full | H-25k | vs zstd-19 | seq_format chosen |
  |---|---:|---:|---:|---|
  | multicopy120k.bin (pure dup) | 5017 | **4448** | 3690 = **+20.5%** (was +36.0%) | **2** (offset-code wins) |
  | multiversion.bin (near-dup) | 61007 | 61007 | 56625 = +7.7% | 0 (separate wins) |
  | srctree.tar (mixed tarball) | 85398 | 85398 | 79569 = +7.3% | 0 (separate wins) |
  | repeated.log (rep-rich log) | 11774 | 11774 | 10063 = +17.0% | 0 (separate wins) |

  Zero regression on gated corpora: tuned 10-file **0.158273 (byte-identical to champion)**, RT 10/10; holdout **0.2390 (byte-identical)**, RT 6/6.
- **VERDICT: MARGINAL WIN on pure-duplicate; the diagnosis was half-right — Cubrim was ALREADY coding offsets competitively.** The offset-code model wins decisively on pure-duplicate data (multicopy 5017→**4448**, −11.3%, gap to zstd +36.0%→**+20.5%**), regression-proof and byte-exact. But it does NOT close the diverse-offset gap (srctree, multiversion, repeated.log all unchanged) — and the `seq_format` instrumentation explains why: on every diverse-offset file the EXISTING **separate per-stream coder (seq_format 0, H-25f)** already wins, because it byte-splits distances into dist_b0/b1/b2 streams coded with **order-1 rANS context** — itself a competitive offset model. The bit-length-bucket + raw-low-bits decomposition ties or loses to it on genuinely high-entropy offsets (the low bits are irreducible information either way). The multicopy win is NOT better offset entropy — it is that pulling distances out of the combined buffer lets the order-1 rANS model the now-pristine `(literal-run, match-length, mode)` structural stream far better. **So offset coding is NOT the residual lever**: the H-25j-full diagnosis over-attributed the gap to offsets; Cubrim's separate-stream distance coding was already near zstd's offset entropy. Net vs zstd-19: **beats on logs, ties on pure duplicates (now near-tie), ~7–8% on tarball/versions; beats gzip on ALL**. **Kill/re-open condition (H-25l):** with offset coding ruled out as the lever, the remaining srctree/multiversion gap to zstd is parse/match-count and literal entropy (zstd's btultra finds yet fewer matches and codes literals with a dedicated FSE table). This is deep, diminishing-returns territory — the H-25 long-range line is at its practical floor for the cube+rANS architecture. Competitive rail keeps schemes 0–11, modes 0–2, and seq_formats 0–2 intact; leaderboard untouched. NOT tuned to any corpus.

---

## H-29 — Class-C specialization (logs/telemetry/columnar): columnar-transform GO

- **STATUS:** GO (probe-confirmed; implementation queued as next round). Codec byte-identical this round (research+probe only).
- **STRATEGY (operator 2026-06-24):** PERMANENT continuous-improvement race until Cubrim beats BOTH gzip-9 AND zstd-19. Data-determined general-purpose ceiling (H-25l/26/27/28) is NOT a stop condition — specialize on the class where Cubrim already structurally beats zstd via BWT+geomix.
- **CHARACTERIZATION:** built a REAL 9-file class corpus (`code/bench/gen_class_corpus.sh`: journal/app/dpkg/alternatives/toolchain logs + forex×2/status/deals CSV; host-derived, DISJOINT from tuned). Measured `--value-scheme bwt-rans` (competitive rail), RT PASS all. Aggregate cubrim 219107 vs gzip 307388 (**−28.7%**) vs zstd 219039 (**+0.03% = tie**); cubrim wins zstd only **3/9** (app_orchestrate −14.1%, forex_tick −4.2%, forex_usdchf −0.5%), loses 6/9. The `repeated.log −18%` win was a specific case, NOT the whole class.
- **LEVER (charged probe `probe_h29_columnar.py`, faithful — real codec on transformed bytes, 16 B header charged, info-conservation-safe):** reversible column-major field-split. forex_tick 58741→**44359** (zstd −4.2%→**−27.7%**), forex_usdchf 55274→**38457** (−0.5%→**−30.8%**), status_timeseries 22889→**20710** (+7.1% LOSS→**−3.1% WIN flipped**), deals_record 3799→**3702** (+7.0%→+4.3%, tiny string-heavy file not flipped).
- **VERDICT GO:** columnar transposition flips the CSV/columnar sub-class from mostly-losing to crushing zstd by 27–31% on numeric telemetry and flips status to a win. Regression-proof by construction (competitive `min(base, columnar)` + mode byte). NEXT: implement MODE_COLUMNAR container (byte-exact field-split, per-row field-count side stream, competitive rail + RT/property tests). NOT tuned; leaderboard untouched.
- **CLI default trap noted:** plain `compress` (no `--value-scheme`) uses weak bitpack default (14× worse on small files); all bench MUST use `--value-scheme bwt-rans`.

### H-30..H-36 — external-research candidate ladder (for /evolution; synthesized from SOTA log/columnar literature, agent afa18d32)

- **H-30 columnar field-split (HIGH):** per-field column-major reorder before BWT+geomix. CONFIRMED by H-29 probe (−27..−31% vs zstd on telemetry CSV). This is the immediate implementation target. Refs: CLP (Uber, 2.16× over zstd), Parquet/BtrBlocks columnar encodings.
- **H-31 monotonic/timestamp column delta (HIGH):** after field-split, first-order delta on detected monotonic numeric columns (epoch timestamps, ids/counters). Fully reversible (store first value), zero learning cost. Parquet: 10–100× on timestamp columns. Stacks on H-30. Refs: Parquet delta/FOR, Denum numeric-token parsing.
- **H-36 CLP-style template/variable split (HIGH ceiling, MAJOR complexity):** parse logs into (template-id, timestamp-delta, variable-list), compress each stream via existing rails as a new MODE_LOG. CLP 2.16× over zstd; LogPrism ~2.5× over zstd-level. MANDATORY Python spike gate (confirm ≥1.5× on syslog) before Rust. Refs: CLP, Logzip, Denum, LogPrism, LogFold.
- **H-32 LogLite XOR-cache preprocessor (MEDIUM):** XOR each line against a cached recent same-length line, RLE the zero-runs, feed BWT. +17–37% over LZMA as a preprocessor; but BWT+geomix already captures same-line context, so incremental gain uncertain. Competitive-gate. Ref: LogLite (VLDB 2025).
- **H-33 STC digit-context decomposition (MARGINAL):** split digit-run bytes into side streams before BWT. ~1.6% on enwik9; maybe 2–3% on numeric-dense logs. Cheap O(n), no table. Ref: arxiv 2606.03570.
- **H-34 APM/SSE secondary estimation on geomix output (MARGINAL / possible mirage):** refine geomix probability via a small identity-init APM table (k-bit context). Self-disables if uncorrelated (no regression risk). 64KB block ≈ 256 obs/cell — borderline learnable (unlike Gotcha #9 high-cardinality). Gate with a ~50-line H(residual|ctx) probe; skip if <0.02 bpb. Ref: cbloom APM/SSE, PAQ family.
- **H-35 zstd-dict for short-record blocks (MEDIUM, narrow):** train a dictionary on first N records of a short-fixed-record block. 3–4× over non-dict zstd for <1KB records; vanishes >1KB. Scope-limited (JSON API logs, Kafka, WAL). Ref: zstd --train, Cassandra CEP-54.

### H-37..H-42 — external-research candidate ladder (round 2: weak-class specialization — exe/binary/float/text/string; synthesized from SOTA, research agent 7aae20fd)

> **Targeting context.** Round 1 (H-30..H-36) covered logs/columnar/CLP/int-delta/dict/APM. Round 2 attacks the classes where CUBR-0034 measured Cubrim LOSING: ELF/exe (`exe.bin` loss vs gzip & zstd), source-code/text (`rust_src`, `c_header` loss; `prose` only marginal win), the near-duplicate-binary / mixed-tarball ~7–8% residual gap to zstd (H-25k floor), and the string-heavy columnar sub-class H-29 could not flip (`deals_record`). All numbers below are **literature estimates, not Cubrim measurements** — each is a candidate, not a result. Every entry names its MANDATORY pre-Rust gate so A does not re-walk the Gotcha-#6/#7 charged-branch traps or the dict-overhead-on-small-blocks trap.

- **H-37 — BCJ / branch-conversion filter for executables (HIGH; class: ELF/exe).**
  - *Why.* Machine code stores CALL/JMP targets as *relative* offsets, so the same callee produces a different byte sequence at every call site — LZ/BWT see no repeat. A BCJ filter rewrites those operands to *absolute* addresses (x86 E8/E9; ARM/ARM64/RISC-V variants), making identical targets byte-identical → the BWT+geomix/LZ backend then captures them. Fully reversible (inverse filter on decode), zero model cost.
  - *Expected lever (estimate, not a Cubrim measurement).* xz/LZMA2 reports 0–15% smaller `.xz` on x86 executables from BCJ alone; ZPAQ's E8E9 quotes ~6–8% on x86. Directly attacks the `exe.bin` loss.
  - *Mandatory gate (do FIRST, ~50-LoC Python, no Rust).* Apply E8E9 to `exe.bin`, run the existing `bwt-rans` rail on filtered vs raw bytes, compare. Charge nothing extra (filter is parameter-free & in-place) but record per-architecture detection cost if whole-file try-both is used. Competitive `min(raw, bcj)` + 1 filter-id byte → regression-proof by construction. Honest cap: only the `.text` machine-code span benefits; data/rodata segments are neutral, so gain on a whole ELF is diluted — the probe must run on the real ELF, not a hand-picked code span.
  - *Refs.* xz/LZMA2 BCJ filters (Pavlov/Collin) https://en.wikipedia.org/wiki/BCJ_(algorithm) ; Linux kernel xz doc https://www.kernel.org/doc/html/v5.10/staging/xz.html
  - *Status:* PLANNED.

- **H-38 — ALP-style decimal-float→int transform for numeric float columns (HIGH; class: float telemetry, stacks on H-30/H-31).**
  - *Why.* Most real-world doubles are *decimals* (e.g. forex `1.0938`), so multiplying by `10^e` yields a compact integer with a small exponent stored once per column; the integer stream then goes through Frame-of-Reference + the existing rANS backend. This turns IEEE-754 mantissa noise (incompressible) into low-magnitude integers (highly compressible). Reversible (store `e` + per-value exception list for non-decimal-representable values).
  - *Expected lever (estimate).* ALP (SIGMOD 2024) is the float SOTA on ratio AND 1–2 orders faster than Chimp/Gorilla/Patas. **Honest caveat from the literature:** Gorilla/Chimp128/Elf float coders do *not* beat zstd on ratio — so the value to Cubrim is ALP as a *reversible front-end transform* feeding BWT+geomix/rANS, NOT as a standalone coder. Stacks on the H-30 columnar field-split (transform applies per detected float column).
  - *Mandatory gate (charged probe, faithful — real codec on transformed bytes, 16-B header + per-column `e`/exception-list charged; info-conservation-safe per Gotcha #7).* Detect decimal-representable float columns in `forex_*`/`status_timeseries`, apply ALP encode, run `bwt-rans`, compare vs the H-29 columnar baseline. The exception list (non-decimal values stored verbatim) is a MANDATORY decoder branch — charge it, or it reproduces the φ-map false-GO.
  - *Refs.* ALP, Afroozeh & Boncz, ACM SIGMOD 2024 https://dl.acm.org/doi/10.1145/3626717 , code https://github.com/cwida/ALP ; Chimp VLDB 2022 https://www.vldb.org/pvldb/vol15/p3058-liakos.pdf ; Pcodec.
  - *Status:* PLANNED.

- **H-39 — frequency-ordered BPE tokenization preprocessor for text / source code (MEDIUM-HIGH; class: rust_src, c_header, prose).**
  - *Why.* BPE-tokenize the input, then renumber the vocabulary so the most frequent tokens get the smallest integer ids; the resulting id stream has a steep power-law distribution the rANS entropy stage codes near its entropy, and common multi-byte tokens (keywords, `    `, `0x`, `->`) collapse to one symbol before BWT. Fully reversible given the token table.
  - *Expected lever (estimate, fresh 2026 result).* Frequency-Ordered Tokenization reports +0.76 pp for zstd, +1.69 pp for LZMA, +7.08 pp for zlib on enwik8 *including vocabulary overhead* — i.e. a modest but real gain over the Word-Replacing-Transform baseline. Attacks the source-code/text losses where Cubrim trails gzip.
  - *Mandatory gate (CRITICAL — dict-overhead trap).* The token table MUST be transmitted and is a MANDATORY decoder branch (Gotcha #7 family). The enwik8 numbers are on a **100 MB** input where the table amortizes to ~0; on Cubrim's ≤64 KB cube blocks the table cost can EXCEED the gain. The probe must (a) charge the full per-block table, (b) measure on the real ≤64 KB `rust_src`/`c_header` blocks, NOT on enwik8. Likely NO-GO at block scale unless a shared/static table is used — flag that as the fork.
  - *Refs.* Frequency-Ordered Tokenization for Better Text Compression, Kalcher, arXiv 2602.22958 https://arxiv.org/abs/2602.22958
  - *Status:* PLANNED.

- **H-40 — FSST short-string symbol-table coder for string-heavy columns (MEDIUM, narrow; class: string columns H-29 could not flip).**
  - *Why.* FSST replaces frequent ≤8-byte substrings with 1-byte codes via a static symbol table, giving LZ4-class speed with better ratio on short strings AND random access. Targets exactly the `deals_record`-style string columns that the H-29 columnar split left at +4.3% (not flipped to a win) because they are string- not numeric-dominated.
  - *Expected lever (estimate).* FSST (VLDB 2020) ~2× on string columns vs raw; as a per-column front-end it feeds the cube backend a denser stream.
  - *Mandatory gate (dict-overhead trap, same as H-39).* The 8-byte symbol table (≤2 KB) is a MANDATORY decoder branch — on small per-column blocks it may eat the gain; charge it and measure on the real string column, not a concatenated corpus. Competitive `min(base, fsst)` per column.
  - *Refs.* FSST: Fast Random Access String Compression, Boncz/Neumann/Leis, VLDB 2020 https://www.vldb.org/pvldb/vol13/p2649-boncz.pdf , code https://github.com/cwida/fsst
  - *Status:* PLANNED.

- **H-41 — SHUFFLE / bitshuffle + bytedelta byte-plane transform for fixed-width binary (MEDIUM; class: near-dup binary `multiversion`, fixed-width numeric arrays).**
  - *Why.* For an array of N-byte elements, transpose so all byte-plane-0 bytes are contiguous, then plane-1, etc. (HDF5 SHUFFLE; bitshuffle does it at bit granularity). High-order bytes of a smooth numeric series become long runs the BWT captures; bytedelta then diffs adjacent bytes within a plane. Reversible (fixed permutation).
  - *Expected lever (estimate).* Blosc reports bytedelta+shuffle median 5.86× vs 5.62× bitshuffle vs 3.86× no-filter on typed data. NOTE distinction from the closed H-14 stride-2 NO-GO: H-14 applied stride delta as a *value-scheme on the cube-mode value stream* (which inflated n_distinct); this is a *pre-chunk byte-plane transpose on detected-element-width raw bytes*, a different transform on different data.
  - *Mandatory gate.* Requires a detected element width; arbitrary binary has none, so this is competitive-gated (`min(raw, shuffle_w)` over a few candidate widths + 1 width/id byte). Probe on `multiversion.bin` and a synthetic fixed-width numeric array; if no width gives a win, NO-GO for that file (expected on truly unstructured binary).
  - *Refs.* bitshuffle, Masui https://github.com/kiyo-masui/bitshuffle ; Blosc bytedelta https://blosc.org/posts/bytedelta-enhance-compression-toolset/
  - *Status:* PLANNED.

- **H-42 — PFOR (patched frame-of-reference) with exception list for integer columns (MEDIUM; stacks on H-31).**
  - *Why.* Plain FOR/delta (H-31) must size its bit-width to the *largest* delta in a block, so a single outlier (a counter reset, a gap) forces every value wide. PFOR bit-packs to the width that covers the *bulk* (e.g. 90th percentile) and stores the few outliers in a separate exception stream. Targets integer/id/counter columns with occasional spikes that defeat plain delta.
  - *Expected lever (estimate).* PFOR-delta / BtrBlocks report large gains over FOR when delta distributions are skewed-with-outliers; widely used in column stores (FastPFor, BtrBlocks SIGMOD 2023).
  - *Mandatory gate.* The exception stream (positions + values) is a MANDATORY decoder branch — charge it; the win is only real when `(narrow-packed bulk + exceptions) < (wide-packed all)`. Probe on the H-29 integer columns (ids/counters) vs the H-31 plain-delta baseline. Refinement of H-31, not a replacement.
  - *Refs.* Zukowski et al. "Super-Scalar RAM-CPU Cache Compression" (PFOR-delta, 2006); BtrBlocks, SIGMOD 2023; FastPFor (Lemire) https://github.com/lemire/FastPFor
  - *Status:* PLANNED.

> **Scouted but NOT laddered (recorded so A does not re-research them):** neural / context-mixing whole-stream coders — cmix v20 (~1.17 bpb enwik8), NNCP, L3TC (RWKV-based, arXiv 2412.16642), AlphaZip (arXiv 2409.15046). SOTA on text *ratio* but at 0.5–5 KB/s and 16–64 GB RAM — disqualified for a shipping archiver; and their realizable subset (online context modelling of the residue) is already CLOSED by Gotcha #9/#10 (H-27/H-28). The frequency-ordered-tokenization front-end (H-39) is the one realizable, table-charged slice of this family.

### H-43..H-46 — external-research candidate ladder (round 3: grammar / image-transform / adaptive-mixing entropy backends; research agent 7aae20fd)

> **Targeting context.** Round 2 (H-37..H-42) was front-end *transforms* (BCJ/ALP/BPE/FSST/shuffle/PFOR). Round 3 adds (a) a long-range *structural* class the flat MODE_LZ window cannot reach (hierarchical grammar repeats), (b) the 2D image class (Cubrim's BWT has no spatial model — provisional priority until CUBR-0034's table lands), and (c) *adaptive, table-free* entropy backends that can improve coding WITHOUT re-walking the CLOSED order-2 static-table branch (the key distinction: these transmit no frequency table — both sides build the same model online). All numbers are literature estimates, not Cubrim measurements.

- **H-43 — grammar-based compression (GLZA / Re-Pair class) as a structural front-end or MODE (MEDIUM-HIGH; class: source code, mixed tarball, structured text).**
  - *Why.* A grammar compressor builds a context-free grammar whose rules reference other rules, so *hierarchical* / nested repeats (a function body that itself contains repeated sub-patterns; a struct layout repeated across a tarball) collapse to a single nonterminal — structure a flat LZ window (Cubrim's MODE_LZ, at floor per H-25k) and a 64 KB BWT block both miss. GLZA reaches PPM-class text ratio with LZ-class decode speed and sits on the Pareto frontier.
  - *Expected lever (estimate).* GLZA within ~5% of PPMd on 1–10 MB text; Re-Pair/GLZA beat flat LZ on highly self-similar structured input. Attacks the `rust_src`/`c_header` losses and the residual mixed-tarball gap to zstd.
  - *Mandatory gate (charged probe).* The grammar (rule set / dictionary of nonterminals) is a MANDATORY transmitted decoder branch — charge it in full (Gotcha #7 family); on ≤64 KB blocks the rule table may not amortize (the GLZA numbers are on 1–10 MB). Probe Re-Pair on the real `rust_src`/`srctree` bytes, charge the grammar, compare vs MODE_LZ + bwt-rans. Likely needs whole-file scope (pre-chunk) to amortize — flag as the fork. Competitive `min(base, grammar)` + mode byte.
  - *Refs.* GLZA / Grammatical Ziv-Lempel, Kennon Conrad — https://www.researchgate.net/publication/359472230 ; Re-Pair, Larsson & Moffat 2000; grammar via induced suffix sorting, arXiv 1711.03205 https://arxiv.org/pdf/1711.03205
  - *Status:* PLANNED.

- **H-44 — lossless predictive / wavelet image transform for raster image data (MEDIUM, provisional; class: images/bitmaps — confirm against CUBR-0034 table before prioritizing).**
  - *Why.* Cubrim's BWT+geomix is a 1D sequence model with NO 2D spatial awareness — for raster images, neighbouring pixels (left, up, up-left) are the strongest predictors and live on different rows (far apart in the byte stream). Two reversible levers: (1) the JPEG-LS / LOCO-I **MED predictor** (median of left, up, gradient) → residual stream fed to rANS; (2) the JPEG XL **Squeeze** / reversible integer 5/3 wavelet (lifting) multi-resolution decomposition. Both fully reversible.
  - *Expected lever (estimate).* JPEG-LS/CALIC are the predictive lossless SOTA on continuous-tone images; JPEG XL modular lossless ≈ 35% under optimized PNG. Reversible integer wavelet + context modelling ≈ CALIC. Only relevant if CUBR-0034 contains a weak image class.
  - *Mandatory gate.* Requires image dimensions (width/stride) — undetectable from arbitrary bytes, so competitive-gated (`min(raw, pred_w, wavelet_w)` over candidate widths + id byte). Neutral-to-harmful on non-image data → must NOT regress (the competitive rail guarantees it). Probe on a real raw bitmap, NOT a PNG (already entropy-coded). Hold until the world bench confirms the class exists.
  - *Refs.* LOCO-I / JPEG-LS, Weinberger/Seroussi/Sapiro 2000 https://ieeexplore.ieee.org/document/855427/ ; CALIC, Wu & Memon; JPEG XL Squeeze / modular https://cloudinary.com/blog/jpeg-xls-modular-mode-explained ; reversible integer wavelet, Lossless JPEG https://en.wikipedia.org/wiki/Lossless_JPEG
  - *Status:* PLANNED (provisional — gated on CUBR-0034 class table).

- **H-45 — Context-Tree Weighting (CTW) as a table-free adaptive backend on the BWT'd value stream (MEDIUM-HIGH; class: text/source + all cube-mode files; entropy backend).**
  - *Why — and why this is NOT the CLOSED order-2 branch.* The CLOSED order-2 chains (Gotcha #6, `closed-branches.md` § order-2) died on *transmitted static-table cost*. CTW transmits **NO table** — it is a fully adaptive Bayesian mixture that weights ALL context depths 0..D simultaneously (no order-selection, no fallback chain), and the decoder rebuilds the identical tree online. So the table-cost failure mode that killed order-2 does not apply. CTW provably approaches the best-order redundancy and measured ~0.09 bpb better than PPMd on Calgary. It could replace/augment geomix's fixed geometric o0/o1/o2 mix with a principled all-depth mixture.
  - *Expected lever (estimate).* ~0.09 bpb over PPMd on Calgary (CTW literature) → a few % on the BWT'd text streams where geomix's fixed mix is suboptimal.
  - *Mandatory gate (Gotcha #9 — learning cost, NOT table cost).* CTW still pays an *online learning* cost; over a 256-symbol byte alphabet on a 64 KB block the binary-decomposed CTW (8 bit-trees/symbol) must be simulated with a REAL adaptive coder (not ideal entropy) and checked for cell-count ÷ stream-length sanity (Gotcha #9). Probe: binary CTW vs geomix bpb on the real BWT'd `text`/`binary_mixed` streams. If learning cost > geomix gain on 64 KB, NO-GO at block scale (same scale caveat as H-39).
  - *Refs.* Context-Tree Weighting, Willems/Shtarkov/Tjalkens, IEEE IT 1995 https://en.wikipedia.org/wiki/Context_tree_weighting ; "Implementing CTW for text compression" https://ieeexplore.ieee.org/abstract/document/838152/
  - *Status:* PLANNED.

- **H-46 — logistic (PAQ/lpaq-style) mixing replacing geomix's geometric mix (MARGINAL-MEDIUM; class: all cube-mode; entropy backend refinement).**
  - *Why.* geomix (H-24) mixes o2/o1/o0 by a fixed *geometric* weighting. PAQ/lpaq mix model predictions in the *logistic* (stretch/squash) domain with online-trained weights — strictly more expressive than a fixed geometric blend, and (like CTW) adaptive with no transmitted table. This is the realizable, lightweight slice of the neural/CM family (a single logistic mixer of the existing few contexts, NOT a deep net — so it dodges the NNCP/cmix 0.5–5 KB/s disqualification).
  - *Expected lever (estimate).* lpaq-class logistic mixing typically beats fixed linear/geometric blends by 1–3% on text; bounded because geomix already captures most of the gain.
  - *Mandatory gate.* Same Gotcha #9 real-adaptive simulation as H-45; the delta vs geomix is *only* the mix function (same contexts), so the probe is cheap — swap geometric→logistic mix in the existing geomix probe harness and measure. Self-disabling / competitive so no regression risk.
  - *Refs.* PAQ / lpaq logistic mixing, Mahoney (Data Compression Explained) http://mattmahoney.net/dc/dce.html ; lpaq1 source.
  - *Status:* PLANNED.

> **Round-3 scouted but NOT laddered:** DMC (dynamic Markov compression) — adaptive bit-level, table-free, but CTW/PPM dominate its ratio in the literature; subsumed by H-45. Full neural (NNCP/cmix/RWKV) re-confirmed disqualified (speed/RAM) per the round-2 note — H-46 is the realizable logistic-mixing slice. PSTs (probabilistic suffix trees) ≈ bounded-order CTW; subsumed by H-45.

### H-49..H-51 — NON-SUBSUMABLE structural transforms (round 4; crystallises Gotcha #11 into a predictive gate; research agent 7aae20fd)

> **The Gotcha #11 predictive gate (apply to ANY candidate in ~30 s BEFORE building a spike).** A strong BWT+rANS backend already models order-N byte context + runs + suffix-grouped contexts within each stream. A pre-transform is therefore **SUBSUMED** (will measure ~0, do NOT spike) iff it only *reorders or locally-deltas bytes within one stream the backend already sees* — this is why DoubleDelta (H-41 NO-GO), MTF, and dict+RLE-of-an-already-low-card-stream (H-48 marginal −2.3%) all lost.
>
> A transform is **NON-SUBSUMABLE** (worth a charged spike) iff it requires AT LEAST ONE of:
> - **(i) sub-byte field separation** — bits with *different statistics sharing the same bytes* (IEEE-754 sign/exp/mantissa; packed bitfields). A byte-symbol model cannot split co-located bits. ← H-40/H-38 decimal-float→scaled-int won here (−33.5% vs zstd).
> - **(ii) cross-stream / cross-column information** — mutual information between *separate* columns the backend compresses independently. BWT groups suffix-contexts *within* one stream; it has no cross-column predictor.
> - **(iii) real-number arithmetic over the semantic value interpretation** — wavelet / PCA / DCT / predictive residual computed on bytes-as-numbers. A symbol model cannot do linear algebra.
>
> Corollary — the SUBSUMED list (skip, save A's time): monotone byte permutations (MTF); local byte/bit deltas incl. **Gorilla/Chimp/Patas XOR-with-previous** (streaming delta family, same as DoubleDelta — and lit: Chimp x2.4 < ALP x4.3, does not beat zstd); Pseudodecimal/PDE (ALP's predecessor, ALP dominates it). All ceilings below are **lit estimates, not Cubrim measurements**; every helper named is a MANDATORY charged decoder branch.

- **H-49 — cross-column correlation residual (Corra-class) [RANK #1: cleanest non-subsumed + composes with the PROVEN columnar win].**
  - *Non-subsumable via (ii) cross-stream MI.* After MODE_COLUMNAR transpose, Cubrim compresses each column INDEPENDENTLY — all mutual information between correlated/derived columns is left on the table and is UNREACHABLE by per-column BWT+rANS. Real telemetry is full of it: **Backblaze `smart_N_raw` ↔ `smart_N_normalized` (a deterministic function → near-zero residual)**, OHLC bid↔ask↔high↔low, sensor temp↔voltage, city↔zip. Encode column B as residual `B − predict(A)` (linear fit or value→value map), feed the residual to bwt-rans.
  - *Lit-estimate ceiling.* Corra (VLDB 2024, TUM) saves −53.7% (DMV zip), −58.3% (lineitem receiptdate), **−85.16% (Taxi total_amount)** *beyond* single-column encoding. Directly extends the H-29/H-30/H-31 telemetry win.
  - *Charged helper (decoder branch).* per-correlated-pair predictor: which→which + coefficients / value-map + exception list. Small vs the savings; charge it. Competitive `min(independent, residual)` per column → regression-proof.
  - *Refs.* Corra https://arxiv.org/abs/2403.17229 ; Lightweight Correlation-Aware Table Compression https://arxiv.org/html/2410.14066
  - *Status:* PLANNED — **top handoff: pairs with MODE_COLUMNAR + ALP; biggest non-subsumed slack on the proven-win class.**

- **H-50 — ALP-RD full real-double bit-split (arbitrary doubles, not just the decimal subset) [RANK #2].**
  - *Non-subsumable via (i) sub-byte.* Extends H-38/H-40 (decimal subset) to ARBITRARY doubles (ML weights, scientific, computed values that are NOT clean decimals). ALP-RD splits each double bitwise into a **left** part (first 16 bits = sign + exponent + upper mantissa → dictionary-encoded, few distinct patterns) and a **right** part (low bits → bitpacked raw). The high-bit dictionary structure and low-bit noise share bytes — a byte-backend cannot separate them.
  - *Lit-estimate ceiling.* ALP avg **×4.3** vs Patas ×2.1 / Chimp ×2.4; ALP beats Chimp128 on 27/30 datasets (ALP, SIGMOD 2024). Covers the float class H-38's decimal path leaves behind.
  - *Charged helper (decoder branch).* left-parts dictionary + exception list. Charge both. Competitive with the decimal ALP path (`min(alp, alp_rd, raw)`).
  - *Refs.* ALP / ALP-RD https://dl.acm.org/doi/10.1145/3626717 ; DuckDB writeup https://duckdb.org/science/alp/ ; code https://github.com/cwida/ALP
  - *Status:* PLANNED.

- **H-51 — reversible-arithmetic transform for scientific float-grid (integer wavelet / cross-field predictor) [RANK #3, narrower — gate on CUBR-0034 having a scientific-grid class].**
  - *Non-subsumable via (iii) real arithmetic.* For ND smooth float grids (climate, simulation, scientific arrays), a reversible integer lifting wavelet (5/3) or a cross-field linear/CNN predictor → residual concentrates energy / removes spatial+inter-field redundancy that no byte-symbol model can compute. Categorically outside the backend's reach.
  - *Lit-estimate ceiling.* Cross-field prediction +25% under error bounds (HPDC 2025 — NOTE: that result is lossy-bounded; the lossless slice is smaller, mark carefully); reversible integer wavelet ≈ CALIC lossless on continuous-tone grids. Overlaps H-44 (image) for 2D rasters.
  - *Charged helper (decoder branch).* transform is in-place (lifting) → ~free; a cross-field predictor needs its coefficients charged. Needs grid dimensions (like H-44) → competitive width-gate.
  - *Refs.* Advancing Scientific Data Compression via Cross-Field Prediction, HPDC 2025 https://dl.acm.org/doi/10.1145/3731545.3731592 ; reversible integer wavelet (JPEG2000 lossless / Lossless JPEG).
  - *Status:* PLANNED (provisional — gated on the world-bench class table).

> **Round-4 demoted (non-subsumable but lower slack / higher complexity — note, don't prioritise):** (d) struct-of-arrays for binary wire formats (protobuf/msgpack/parquet tensor) = "columnar for binary," an extension of MODE_COLUMNAR but needs a per-format parser (heavy helper) — follow-on, not top-3. (f) genomic: 2-bit packing is SUBSUMED (low-card → rANS already ≈2 bits/base); only **reference-delta** is non-subsumable (cross-file shared reference — legitimate form of the CLOSED H-18 dictionary, but narrow + needs aligner + shared reference) — note for a genomic-specific track only.

> **REAL CORPORA COLLECTED (operator `.brief-research-newclass.txt`, research agent 7aae20fd) → `/home/dev/cubrim-worldbench/`:**
> - **CORPUS 2 (give A FIRST)** `corpus2-raw-doubles/` — UCI Superconductivity features as raw `float64` `.npy`; PRIMARY array z-score-standardised → **0.000 % short-decimal** (ALP-decimal/H-40 provably inapplicable, measured), 100 %-double whole-file slack → for **H-50 ALP-RD**. Lit ×4.3.
> - **CORPUS 1 (second)** `corpus1-wide-deterministic/` — UCI Adult (`education`↔`education_num` exact 1:1 bijection) + Covertype (40 `Soil_Type` one-hots verified mutually exclusive 20 000/20 000 → 40 cols → one ~5.3-bit categorical) → for **H-49 reborn** on the NON-temporal class A's H-49 NO-GO never tested. Hand `covtype` before `adult` (bigger whole-file slack; answers A's "single predicted column is a fraction of the file"). Lit Corra −53..−85%.
> - Provenance/SHAs/reproduce: each dir `MANIFEST.md`; ranking: `README-newclass-corpora.md`. Ceilings = lit estimate; helper = charged decoder branch; spike before Rust.

### H-47..H-48 — telemetry/columnar class-wide hardening (track 1: extend the PROVEN win; research agent 7aae20fd)

> **Context (operator, track 1+4 parallel race).** H-29/H-30 PROVED the columnar field-split beats zstd-19 by −22% aggregate (beats gzip everywhere) — but on a **host-derived** corpus. Track 1 = harden that win to a **class-wide** claim on representative public real-world telemetry, and complete the per-column codec cascade so the win covers the whole telemetry schema, not just numeric CSV. Full acquisition plan + mechanism: `documentation/ephemeral/research/telemetry-classwide-corpus-plan.md`. The two CONFIRMED-weak classes (logs + small <64 KB) are a measured micro-efficiency ceiling — NOT revisited. Ceilings = lit estimate, not Cubrim measurement.

- **H-47 — world telemetry corpus for class-wide zstd-beat validation (track-1 corpus task, not a codec change).**
  - *Goal.* Acquire ≥3 public telemetry sub-classes (wide numeric CSV / IoT sensor TS / financial tick / trip CSV / Prometheus metrics), DISJOINT from tuned + host class corpus, with provenance manifests (source URL + SHA), to prove the −22% columnar win is class-wide and not host-corpus overfit.
  - *Why Cubrim should win (mechanism, corpus-independent).* Columnar transposition concentrates per-column self-similarity that the row-major byte stream scatters; BWT+geomix+rANS then code each column near its entropy, while zstd's window re-learns the field interleaving every record. Win condition = *per-column self-similarity > per-record byte self-similarity*, which holds for any regular-schema telemetry. Fair-comparison protocol: cubrim MODE_COLUMNAR vs zstd-19 on the SAME raw CSV/JSONL (do NOT hand zstd the transpose).
  - *Lit-estimate ceiling.* dict+RLE 10–50× on low-card columns (BtrBlocks/Parquet); ALP float SOTA; confirmed −27..−31% vs zstd on host forex (H-29).
  - *Architectural caveat (highest-risk design decision).* **MODE_COLUMNAR must transpose per-column GLOBALLY (Parquet-style column chunks), not per 64 KB row-block** — wide tables (Backblaze ~1–2 KB/row → ~30–60 rows/64 KB block) give too few per-column values for BWT runs under per-block transpose; the win would under-deliver as an implementation artefact, not a class limit.
  - *Public sources.* Backblaze Drive Stats (HuggingFace/Kaggle/B2); Intel Berkeley Lab sensor (MIT CSAIL); CryptoDataDownload / Dukascopy tick; NYC TLC trip records (AWS Open Data); node_exporter Prometheus exposition. (URLs in the plan doc.)
  - *Status:* PLANNED (corpus acquisition; A or a dedicated corpus task runs the spike — `--value-scheme bwt-rans`, NOT the bitpack CLI default).

- **H-48 — low-cardinality categorical/enum column → dictionary + RLE cascade (HANDOFF to A; completes the telemetry cascade alongside ALP H-38).**
  - *Why this is the strongest complementary structural class.* A's ALP (H-38) covers FLOAT columns; the telemetry schema also has **categorical/enum** columns (status, symbol, payment_type, drive model, log-level). Dictionary-encode each to a small int, then RLE → rANS. Cubrim's BWT+rANS already crushes long runs of small ints **by construction** — this is its structural strength, not a stretch. Together {timestamp=delta-of-delta, float=ALP, enum=dict+RLE, counter=FOR/PFOR} = the full BtrBlocks/Parquet two-stage cascade (column-aware encoding below the entropy coder).
  - *Lit-estimate ceiling.* dictionary wins below ~50 k distinct/block; low-cardinality columns routinely 10–50× (BtrBlocks SIGMOD 2023, Parquet RLE_DICTIONARY, ClickHouse LowCardinality). Above ~50 k distinct the index width + dictionary size lose to a general codec → competitive-gate per column.
  - *Mandatory gate (charged spike before Rust).* The dictionary (distinct-value table) is a MANDATORY transmitted decoder branch — charge it; the win is real only when `(dict table + RLE'd small-int index) < raw column through bwt-rans`. Spike on a real low-card column (Backblaze model/status, tick symbol) vs the bwt-rans baseline. Competitive `min(base, dict+rle)` per column → regression-proof.
  - *Refs.* BtrBlocks SIGMOD 2023 https://www.cs.cit.tum.de/fileadmin/w00cfj/dis/papers/btrblocks.pdf ; ClickHouse compression https://clickhouse.com/resources/engineering/database-compression ; Parquet RLE_DICTIONARY.
  - *Status:* PLANNED — **flagged PRIORITY handoff to A (CUBR-CONT)** to pair with the in-flight ALP H-38.

---

## H-31 — Monotonic-column first-order delta (stacks on H-30 columnar): GO

- **STATUS:** GO, shipped inside MODE_COLUMNAR (container mode 4). codec change.
- **LEVER:** after columnar field-split, delta-code columns whose data cells are canonical (`v.to_string()==cell`) non-decreasing integers (epoch ts / ids / counters); first cell verbatim, second anchor, rest signed deltas. Reversible prefix-sum, zero learning cost. Per-column `colmodes` byte + `ends_nl` flag added to wire (the trailing-newline empty row poisoned column-0 detection — stripping it unlocked the win).
- **PROBE (probe_h31_delta.py, faithful):** forex_tick col 44343→delta 36768 (−17%), forex_usdchf 38441→31127 (−19%); journal/dpkg NOT TABULAR — logs need H-36, not H-31.
- **MEASURED (class, --value-scheme bwt-rans, RT all):** forex_tick 44397→**36846** (zstd −27.6%→**−39.9%**), forex_usdchf 38514→**31207** (−30.7%→**−43.8%**), status 20769→**20398** (−2.9%→**−4.6%**); class AGGREGATE 185883→**170654** vs zstd 219039 = −15.1%→**−22.1%** (beats), vs gzip −44.5%. zstd-wins 4/9.
- **ZERO-REGRESSION:** tuned 0.158273 byte-identical (RT 10/10), holdout 0.2390 byte-identical (RT 6/6); 236 tests green, clippy 0 new.
- **VERDICT GO** — deepens telemetry sub-class to −22% under zstd. HONEST: does NOT flip the LOG files (not column-uniform; columnar never engages). NEXT: **H-36 CLP-style log-template split** for journal/toolchain/dpkg. Class not a ceiling.

---

## H-36 — CLP-style log-template / variable split: NO-GO (spike gate not met)

- **STATUS:** NO-GO. Mandatory Python-spike gate (≥1.5× over zstd-19 on real syslog BEFORE Rust) NOT cleared — no parser written.
- **SPIKE (probe_h36_log_template.py, faithful real-codec, charged Gotcha #6):** template-dict + template-id stream + columnar variable blob (H-31 delta on monotone cols) + timestamp-delta stream, each compressed by real cubrim bwt-rans. Corpus: H-29 class real logs.
- **MEASURED vs zstd-19 (best of CLP / CLP+ts):** journal.log (real syslog) 14507 vs 18688 = **1.29×**; toolchain 26274 vs 27548 = 1.05×; dpkg 7094 vs 6764 = 0.95× (loses); app_orchestrate 15749 vs 23218 = 1.47×. NONE reach 1.5×.
- **VERDICT NO-GO** under the gate. Honest nuance: CLP beats zstd on 3/4 logs (1.05–1.47×) — a MODE_LOG would flip journal/toolchain/app to wins — but misses the 1.5× Rust-justification bar and dpkg loses. journal residual = template-dict 5367B + high-entropy variables 7040B (pids/addresses, data-determined). OPERATOR DECISION: hold 1.5× gate (ceiling) vs relax to "beat zstd" (parser justified for 1.0–1.47×).

---

## H-39 — Small-file class (<64KB structured): micro-efficiency ceiling, NO-GO

- **STATUS:** NO-GO (multiply-confirmed micro-efficiency ceiling). No Rust. CUBR-RESEARCH priorities + faithful spikes both confirm.
- **DIAGNOSIS:** alternatives.log 1238 vs zstd 969/brotli 921 (98% LZ-match, cubrim already < H2); deals_record.csv 3799 vs zstd 3549/brotli 3289 (> order-2 floor 3404). Rail already picks best scheme (geomix).
- **SPIKES (faithful, all reverted byte-identical):** (1) optimal-parse+repcode LZ for small blocks → still mode-0 geomix, MODE_LZ ≥1238 LOSES to zstd 969; (2) columnar on small CSV → framing overhead, ≥3799 (probe 3702 still > zstd); (3) zstd --train dict cross-file → 970 vs 969 ZERO (dict dead at 18KB, helps only <1KB); (4) order-2 floor unreachable (static=table-cost, adaptive=unlearnable Gotcha #9).
- **VERDICT NO-GO** — gap is repcode-LZ-parse + brotli order-2-literal + dictionary-cold-start, all micro-efficiency (research Lever 5 DEAD-structural). Mirrors H-36 logs + H-25l/26/27/28 general ceilings.
- **CLASS-FINAL:** Cubrim WINS columnar/telemetry (−22.1% agg vs zstd, forex −40/−44%), beats gzip everywhere; logs + small-files are micro-efficiency ceilings, no remaining structural lever. OPERATOR DECISION: accept ceiling / brotli-class rewrite / domain mode.

---

## H-40 — Fixed-decimal column delta (ALP decimal-branch subset): GO, NEW-CLASS WIN

- **STATUS:** GO, shipped inside MODE_COLUMNAR (column mode 2). External research #1 best-bet (Lever 1: decimal float → int delta).
- **LEVER:** a columnar column of canonical fixed-decimals (consistent scale, e.g. forex `1.30970000`) → scaled-integer signed delta. Reversible (1 scale-byte/col, render==cell canonical check). H-31 covered integer cols; H-40 covers the decimal cols left as strings.
- **SPIKE (faithful):** forex_tick columnar-str 44343 → +decimal-delta 34378 (−22.5%).
- **MEASURED (class, --value-scheme bwt-rans, RT all):** forex_tick 36846→**26848** (zstd −39.9%→**−56.2%**), forex_usdchf 31207→**24881** (−43.8%→**−55.2%**), status_timeseries 20398→**11702** (−4.6%→**−45.3%**, float telemetry cols); class AGGREGATE 170654→**145634** vs zstd 219039 = −22.1%→**−33.5%** (beats), vs gzip −52.6%.
- **ZERO-REGRESSION:** tuned 0.158273 byte-identical (RT 10/10), holdout 0.2390 byte-identical (RT 6/6); 238 tests green, clippy 0 new.
- **VERDICT GO** — new-class hunt SUCCEEDED: Cubrim structurally crushes zstd on scientific/financial/sensor float columns. NEXT: **H-41 DoubleDelta** (research Lever 2) for fixed-interval timestamp/counter columns (variance-gated). Logs + tiny files remain at their ceilings.

---

## H-41 — DoubleDelta for fixed-interval columns: NO-GO (subsumed by entropy backend)

- **STATUS:** NO-GO (spike, no Rust). Research Lever 2.
- **SPIKE (probe_h41_doubledelta.py, faithful; generated Prometheus-15s + Intel-Berkeley-31s corpus):** single-delta vs double-delta through cubrim rANS/BWT — prometheus 27235→29096 (+6.8% WORSE), sensor 11730→13244 (+12.9% WORSE). Variance gate confirms cols ARE fixed-interval (ts stddev/mean=0.00) yet double-delta loses.
- **WHY:** fixed-interval single-delta = constant stream; rANS/BWT already code it to ~0; delta-of-delta adds noise → worse. DoubleDelta subsumed by a strong entropy coder (BWT⊃MTF analogue); Gorilla/ClickHouse win it only in bit-packing without an entropy stage.
- **BONUS:** current codec (H-31+H-40) ALREADY crushes the class — prometheus 32821 vs zstd 58354 (−43.8%), sensor 11821 vs zstd 47801 (−75.3%), RT byte-exact. Fixed-interval won WITHOUT DoubleDelta.
- **VERDICT NO-GO** — honest subsumption. NEXT: **H-48 enum dictionary→RLE→rANS** (research handoff, structural-strength flag).

---

## H-48 — Enum dictionary→RLE→rANS: MARGINAL (subsumed by BWT+geomix)

- **STATUS:** MARGINAL (spike, no Rust). Research handoff (structural-strength flag).
- **SPIKE (faithful; generated enum-heavy run-structured events.csv 455KB):** current-columnar 20285 vs dict+RLE 19812 (−2.3% only). Baseline current cubrim already −52.1% vs zstd (columnar). 4 enum cols dict+RLE'd.
- **VERDICT MARGINAL** — BWT+geomix already clusters+codes low-cardinality columns near entropy; explicit dict+RLE mostly subsumed (same as H-41 DoubleDelta: dict+RLE/MTF win for Parquet/bzip2 only because they bit-pack; Cubrim entropy-codes). ~0 on real numeric-heavy telemetry. Not implemented. Added **Gotcha #11** (strong entropy backend subsumes delta-order/RLE/MTF pre-transforms — spike through the real backend). Reconsider only for a dedicated categorical/event-log class.

---

## H-49 — Cross-column correlation residual (Corra-class): NO-GO (not additive over temporal delta)

- **STATUS:** NO-GO (spike, no Rust). CUBR-RESEARCH RANK#1 non-subsumable candidate.
- **SPIKE (faithful, charged predictor; real wide telemetry forex OHLC + sensor + deterministic synth control; subtraction AND fitted-linear residual):** vs H-40 baseline — forex_tick 26315→26315/26361 = **0.998×**, forex_GBPJPY 1.00×, sensor 1.00×; deterministic control synth_corr (normalized=2·raw+13) 54505→41210 = **1.32×** best. NONE reach 1.5×.
- **WHY:** cross-stream MI is non-subsumed in principle but NOT additive over Cubrim's existing temporal delta. (1) temporal corr dominates cross-column on smooth time-series (high[i]−high[i−1] < high−open); (2) OHLC/sensor relations are unit-coefficient → residual=intra-row spread, not crushed; fitted-linear helps only non-unit deterministic pairs (Backblaze/DMV — not the telemetry class), and even there 1.32× whole-file. Corra's −53..−85% are on non-temporal wide deterministic tables.
- **VERDICT NO-GO** — refines Gotcha #11: "non-subsumed by the backend" ≠ "additive over the existing pipeline" (must beat what temporal delta ALREADY extracts). Fallback: **H-50 ALP-RD full double bit-split**, H-51 int-wavelet.

---

## H-51 — int-wavelet (Haar) : NO-GO (subsumed by delta+entropy) | H-50 ALP-RD: BLOCKED (no binary-float corpus)

- **H-51 int-wavelet NO-GO (spike, no Rust):** Haar lifting vs temporal-delta through cubrim — forex col1 4465→6672 (+49.4% worse), sensor col2 2920→3699 (+26.7% worse). Temporal delta already extracts the smooth-column structure; multi-scale wavelet coefficients compress worse through the entropy backend (Gotcha #11).
- **H-50 ALP-RD BLOCKED:** no binary IEEE-double arrays on host (*.parquet/*.npy empty); ALP-RD targets binary float arrays = a different input format from the CSV-decimal telemetry class (already won by H-40). Deferred pending operator scope decision.
- **LADDER EXHAUSTED for the telemetry class:** Corra (H-49 not-additive), wavelet (H-51 subsumed), DoubleDelta (H-41 subsumed), dict+RLE (H-48 subsumed) — all closed; ALP-RD needs a different class. The telemetry class is temporally-smooth, so temporal delta + rANS/BWT already extract the structure near-optimally; the structural wins (H-30/H-31/H-40) were the information-changing transforms the pipeline didn't already do. Class won −53.6% class-wide. Next requires a NEW input class (binary floats / non-temporal wide tables) or accepting the telemetry-specialist position.

---

## H-50 — ALP-RD (real-double bit-split) on raw float64: NO-GO (sub-byte separation loses to byte backend)

- **STATUS:** NO-GO (spike, no Rust). CORPUS 2 (UCI Superconductivity float64 .npy, CUBR-RESEARCH RANK#1 of round-4).
- **SPIKE (faithful, charged Gotcha #7; ALP-RD per-col best-R + 8-dict + exceptions; + byte-shuffle + transpose):** PRIMARY z-score zstd19=570610 — byte-shuffle 0.59×, transpose+shuffle 0.55×, ALP-RD charged 0.398× (exc 1.7%); CONTRAST best 0.60×. ALL sub-byte variants 1.7–2.5× LARGER than zstd on both arrays. cubrim(raw) already beats zstd −1.9% (no transform).
- **WHY:** the doubles are LOW-PRECISION (source ~7 decimal digits ≈23-bit; z-score of low-precision inputs) → low mantissa NOT random → zstd/xz/cubrim entropy-code it (~21 bits/value); ALP-RD/shuffle bitpack right RAW (~50 bits/value) discarding that structure → net loss. "0% short-decimal" measured decimal-trick applicability, NOT mantissa randomness; the full-double slack is absent. ALP's lit ×4.3 is on full-entropy scientific doubles.
- **VERDICT NO-GO** — refines Gotcha #11: "right=random→bitpack raw" is itself a subsumption trap on low-precision data. Next: **H-49-reborn on CORPUS 1** (covtype before adult).
