---
artifact: hypothesis-log
task: CUBR-0003
created: 2026-06-17
---

> 🔒 **СЕКРЕТНО — внутренний артефакт.** Журнал гипотез механизма Cubrim. Живёт ТОЛЬКО в приватном репо `Arcanada-one/cubrim` (`Projects/Cubrim/consilium/`) и в gitignored `datarim/`. НИКОГДА не попадает в `Projects/Cubrim/docs/`, README или любую публичную поверхность.

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
