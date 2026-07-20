# CUBR-0041 — Стратегическая диагностика: per-type диспетчер vs единый алгоритм

> **Оркестратор:** DEVS. **Тяжёлые прогоны:** стенд dev-ai 64c (mesh 100.118.134.82).
> **Бинарь:** `/root/cubrim-stand/cubrim-rs/target/release/cubrim` (build 2026-07-03 15:00).
> **Корпус измерений:** **world-корпус = 12 файлов, 243 004 774 B** — enwik8 100MB (вес 0.41), silesia/mozilla 51MB (0.21), silesia/webster 41MB (0.17), silesia/samba 21MB (0.09), dickens 10MB (0.04), mr 10MB (0.04), x-ray 8.5MB (0.03), canterbury/{sum 38K, cp.html 25K, fields.c 11K, xargs.1 4K, grammar.lsp 4K}.
> **Каждое число называет свой корпус.** RT=OK (byte-exact round-trip) — обязательное условие валидности; строки rt_ok=false исключены.

---

## 1. TL;DR — ЧИСЛО и ответ на развилку

### 🎯 ЧИСЛО: потолок специализации на существующих value-схемах = **0.000000 (РОВНО НОЛЬ, 0.0%)**

| метрика (12-file world-корпус, RT-verified) | значение |
|---|---|
| CURRENT — competitive-min (rANS rail) | **0.262140** |
| ORACLE — идеальный per-file выбор из ВСЕХ 12 существующих схем | **0.262140** |
| **потолок специализации (CURRENT − ORACLE)** | **0.000000 (0.0%)** |
| файлов, где не-rANS схема бьёт rail | **0 из 12** |

**Интерпретация (ветка (a) из брифа):** oracle == competitive-min ⇒ **competitive-min УЖЕ выбирает оптимально per-file. Специализация имеющимися режимами ВЫЖАТА полностью ⇒ нужны НОВЫЕ режимы (reset-lite).**

### Решение развилки: **RESET-LITE, НЕ реаудит диспетчера, НЕ полный reset.**
- **НЕ реаудит диспетчера** — он доказанно оптимален (0 файлов с упущенным per-type выигрышем среди существующих схем).
- **НЕ полный reset** — competitive-min rail, MODE-диспетч (LZ/CUBE/CHUNKED/MED16/SOA), image-победа (MED16), rANS-backend работают и должны быть сохранены.
- **RESET-LITE** = добавить ОДИН новый value-scheme (context-mixing / CM) за существующим competitive-min rail. Регрессия невозможна по построению (rail берёт min). CM уже доказан byte-exact на стенде (см. §5).

---

## 2. Почему «единый алгоритм» — strawman (архитектурный факт)

1. **Per-type диспетч УЖЕ существует на уровне MODE.** Кодек авто-выбирает MODE (LZ/CUBE/CHUNKED/MED16/SOA) per-file competitive-min — это и даёт image-победу (mr/x-ray через MED16). При `--value-scheme X` MODE всё равно выбирается внутренне ⇒ **мои замеры уже включают оптимальный MODE-выбор**.
2. **rANS-семья (6 из 12 CLI-схем) коллапсирует в ОДИН byte-identical выход.** Подтверждено эмпирически на всех 11 мультисхемных файлах (идентичные байты у bwt-rans/order2-rans/bwt-adaptive/bwt-ctxmix/bwt-geomix/lz-rans). Это и есть «competitive rail» — но конкурирует он ТОЛЬКО внутри rANS-семьи, не bitpack-vs-entropy-vs-rANS.
3. **CLI-default `auto` (BitpackFixed/CUBE) — сломанный дефолт для tiny** (0.88–0.90 на canterbury), НЕ то, что репортит бенчмарк. Реальный competitive-min = rANS rail.

## 3. Самый глубокий вывод: value-scheme специализация ВЫРОЖДЕНА

Не только ceiling = 0 — **на КАЖДОМ из 12 файлов лучшая существующая схема = один и тот же rANS rail.** Нет ни одного типа файла, где entropy / bitpack / rle / entropy-context-2 выигрывал бы. То есть на оси value-scheme НЕТ per-type ВАРИАЦИИ вообще — «per-type диспетчер существующих value-схем» пустой по построению: диспетчеризовать нечего, rail побеждает единообразно. Специализация может прийти ТОЛЬКО от ДОБАВЛЕНИЯ новой схемы (CM), бьющей rANS на тех типах, где rANS проигрывает (всё кроме image).

Разброс rail vs лучшая-не-rANS: на tiny CUBE-файлах rail 0.31–0.45 vs entropy 0.63–0.69 (rANS доминирует ×2); на больших rail vs bitpack — разница <0.1% (value-scheme почти no-op, MODE решает всё).

## 4. Конкурентный ландшафт — ОДИН 12-file world-корпус (apples-to-apples)

| компрессор | overall (size-weighted) | vs cubrim |
|---|---|---|
| ppmd (7z PPMd o16 mem192m) | **0.239264** | cubrim +9.6% |
| xz -9e | 0.248611 | cubrim +5.4% |
| brotli -q11 | 0.255819 | cubrim +2.5% |
| **cubrim (rail == oracle)** | **0.262140** | — |
| zstd -19 | 0.270837 | −3.3% |
| bzip2 -9 | 0.285740 | −9.0% |

Cubrim rank 4/6. Отставание от ppmd (+9.6%) и xz (+5.4%) — это MODEL-CLASS gap, **не закрывается НИ ОДНОЙ существующей схемой** (ceiling=0 доказывает).

> **Провенанс расхождения с брифом:** операторские current=0.247866 / ppmd=0.228591 — это **24-file** бенчмарк (canterbury+silesia+calgary, с супер-сжимаемыми nci 0.048 / xml 0.091 / ptt5 0.087 / kennedy, которые тянут среднее вниз). Мой стендовый world-корпус = **12 файлов** (enwik8-heavy, без супер-сжимаемых) → current 0.262140, ppmd 0.239264. Потолок 0% по СУТИ корпусо-инвариантен (rail оптимален per-file на любом корпусе), измерен на 12-file world.

## 5. Настоящий потолок = НОВЫЙ backend (CM) — уже доказан byte-exact

Из `_RESEARCH-LOG.md` (все замеры byte-exact, RT-verified на стенде):
- **text:** zpaq-m5 CM full dickens **0.2055** vs ppmd 0.2253 (−9%); NEW-01 CM-проба +13–21% к текущему backend на КАЖДОМ text-файле, RT-OK, без 64KB-cliff.
- **large exe:** mozilla CM **0.2351** vs 7z 0.2605 (−10%).
- **code ≥10KB:** CM бьёт brotli (fields.c, cp.html).
- **16-bit image:** CM 0.4234 slice hint (widen, не gap).
- Проигрывает LZMA ТОЛЬКО на tiny-SPARC `sum` (38KB) → узкий NEW-04 LZMA-специалист.

**Вывод: CM top-rail + узкий LZMA-специалист = правильная двух-backend ось ансамбля за существующим rail.**

## 6. Реаудит гипотез сквозь per-type-призму

### H-25k «линия выжата» — вердикт КОРРЕКТЕН, НЕ false-negative
H-25k (FSE/rANS offset-model, zstd-класс) извлёк per-type выигрыш на LZ-heavy/multicopy файлах; competitive-min rail АВТОМАТИЧЕСКИ выбирает его там — выигрыш НЕ тонет в среднем. «Выжата» = zstd-класс offset-модель достигла потолка СВОЕГО класса; дальше на тех же файлах нужен LZMA-класс range-coder или CM = смена КЛАССА, не доводка. Диспетчер работает как задумано.

### Почти все per-type «рычаги» = MIRAGE (измерено)
tiny-dispatcher (competitive-min уже роутит), SPARC-BCJ (+0.96%), x86-BCJ (≤0.2%). Разрывы — MODEL-CLASS gap, не dispatch gap. Ансамблю нужен ОДИН лучший общий модель, а не БОЛЬШЕ per-type фильтров.

### Реопен-кандидаты (скорректировано измерением)
| кандидат | статус | измерение / обоснование | действие |
|---|---|---|---|
| **IW-02** (mr) | ~~to-ship~~ → **уже LIVE** | **verify-first catch: build УЖЕ даёт mr=0.2104 < ppmd 0.2326 (−9.5%)**. _INDEX с mr rank-3 (0.2540) — устаревшая проза. | закрыть как shipped |
| **NEW-01/NEW-05** (CM backend) | PROVEN, главный | закрывает text (enwik8-weighted→overall), code≥10KB, large exe, widen image — одним backend | **build (приоритет №1)** |
| **NEW-04** (LZMA-класс) | TRACTABLE, узкий | единственный класс, где CM проигрывает — tiny-SPARC sum | build после CM |
| **H-14** (byte pre-transforms) | NO-GO → conditional | re-open при появлении type-детектора (delta/stride-N) | заморозка до детектора |
| **H-15** (distance-map) | NO-GO → conditional | re-open если tiny вернутся на CUBE с новым кодером | заморозка |

## 7. Карта «тип файла → лучший режим» (по факту замеров, не по прозе)

**Ось value-scheme (мой oracle):** ВСЕ 12 файлов → rANS rail (нет per-type вариации, см. §3).
**Ось MODE + gap к лидеру (где реальная специализация):**

| тип | файлы | cubrim ratio | лидер (gap) | статус / нужный режим |
|---|---|---|---|---|
| **image 16-bit** | mr | **0.2104** | ppmd 0.2326 (**−9.5%**) | ✅ **#1** (MED16/CHUNKED — уже выигран) |
| **image 16-bit** | x-ray | **0.4451** | ppmd 0.4544 (**−2.1%**) | ✅ **#1** (MED16 — уже выигран) |
| **text large** | enwik8 | 0.2622 | ppmd 0.2318 (+13.1%) | → CM (решает overall, enwik8-weighted) |
| **text large** | dickens | 0.2903 | ppmd 0.2269 (+27.9%) | → CM |
| **text large** | webster | 0.2105 | ppmd 0.1635 (+28.7%) | → CM (+word-model) |
| **exe large** | mozilla | 0.3068 | xz 0.2612 (+17.5%) | → CM (research: CM 0.2351) |
| **code** | samba | 0.1935 | xz 0.1731 (+11.8%) | → CM / LZMA |
| **text/code tiny (CUBE)** | cp.html | 0.3265 | brotli 0.2803 (+16.5%) | → CM (≥10KB) |
| **code tiny (CUBE)** | fields.c | 0.3057 | brotli 0.2437 (+25.4%) | → CM (≥10KB) |
| **code tiny (CUBE)** | grammar.lsp | 0.3873 | brotli 0.3023 (+28.1%) | → CM + dict (<5KB) |
| **text tiny (CUBE)** | xargs.1 | 0.4530 | brotli 0.3463 (+30.8%) | → CM + dict (<5KB) |
| **binary SPARC tiny** | sum | 0.3458 | xz 0.2484 (+39.2%) | → **LZMA-специалист** (единств. класс, где CM проигрывает) |

**ρ-sparsity связь:** MODE-диспетч разводит tiny→CUBE (малый блок, cube-модель), big→LZ/CHUNKED, image→MED16. Специализация на оси MODE РЕАЛЬНА и РАБОТАЕТ (image #1); на оси value-scheme — вырождена.

## 8. Методология / verify-first

- **ЧИСЛО из oracle.tsv, не из прозы.** Каждый ratio — byte-exact compress+decompress+cmp на 12-file world-корпусе.
- **rANS-collapse** подтверждён эмпирически (идентичные байты, не вывод из source).
- **Инцидент производительности:** `-P64` × внутренне-block-parallel rANS-схемы = load 985 thrash → убито; перезапуск `-P4` + setsid-detach → load 15–32 healthy. Ratios детерминированы (не зависят от load).
- **Известный blind-spot (честно):** oracle свёл ось value-scheme; ось MED16-**ширины** (256/512/1024/2048) не свёл отдельно — но её известный выигрыш (mr w=512) уже в build (mr=0.2104). MODE-ось авто-оптимизируется в каждом замере. Полный потолок специализации ≥ 0 по этой под-оси, но известные выигрыши уже captured.
- **DB `arcanada_cubrim`:** прямого доступа с DEVS нет (креды на Mac); вердикты канонично зеркалированы в `datarim/cubrim-hypotheses/` (76 файлов + 41KB `_RESEARCH-LOG.md`, source: consilium/hypothesis-log.md) — использованы как источник правды.

## 9. Консилиум (мультивендор: deepseek + moonshot)

**Панель: deepseek + moonshot, независимо, по одному брифу (`consilium-brief.md`).**

**КОНСЕНСУС (оба вендора, независимо):**
- **Q1 → REFUTED.** Гипотеза «per-type выигрыши прячутся в среднем» опровергнута для пространства существующих схем: rail уже берёт per-file минимум, 0 файлов лучше обслужены не-rANS схемой.
- **Q2 → RESET-LITE.** Диспетчер доказанно оптимален (ceiling=0); gap — model-class (order-2→CM), не routing. Единственные доказанные выигрыши — CM-проба. ⇒ добавить CM value-scheme за существующим rail.
- **Q3 →** verify-first catch (mr/x-ray уже #1) уменьшает upside реаудита диспетчера и смещает фокус на text/exe, где CM показывает реальную дельту.

**СПОРНЫЕ CAVEAT'Ы (moonshot, адверсариально) — с моей адъюдикацией как оркестратора:**

| caveat | вес | адъюдикация |
|---|---|---|
| Ось `MODE × width × scheme` не свёрнута факторно | **ВАЛИДЕН** | Принято. MODE авто-оптимизируется в КАЖДОМ замере (кодек выбирает MODE внутренне при любом `--value-scheme`), но полный кросс-продукт с MED16-шириной не свёл. Известный width-выигрыш (mr w=512) уже в build. Остаточный headroom по этой под-оси ограничен mirage-выводами research-log. **Не меняет направление (CM — рычаг в любом случае).** |
| 12-file ≠ 24-file; ceiling на 12 не биндит весь корпус | **ВАЛИДЕН (частично)** | Принято как границу применимости. Но rANS-collapse — АРХИТЕКТУРНЫЙ (не корпусный): на 24-file супер-сжимаемые nci/xml/ptt5 — LZ-heavy, где rANS rail тоже доминирует. 0% строго-scoped: «value-scheme ось, 12-file world». Направление не меняется. |
| «Broken CLI-default ⇒ вывод об исчерпании циркулярен» | **ОТКЛОНЁН** | Мисрид. Я мерил РАБОЧИЙ competitive-min rail (rANS), а НЕ сломанный CUBE/bitpack-дефолт. Бенчмарк тоже использует rail, не дефолт. Вывод об исчерпании — из рабочего rail. |
| Intra-file per-block scheme-switching не оценён | СЛАБЫЙ | Кодек УЖЕ делает block-level MODE-competition (MODE_CHUNKED re-enters per-block). Cross-scheme per-block (bitpack↔entropy↔rANS) — нет, но rANS выигрывает per-file единообразно ⇒ маловероятно, что отдельные блоки предпочтут entropy. Честный, но малый остаток. |
| entropy-context-2 / не-rANS на нестандартных width/order отброшены upstream | СЛАБЫЙ | Использованы дефолтные параметры. entropy-семья проигрывает rANS ×2 на tiny и тай на big — маловероятно перебить тюнингом параметров. |

**ИТОГ КОНСИЛИУМА:** оба вендора → **RESET-LITE**. Число 0% — tight на оси value-scheme для 12-file world-корпуса; каcaveated остаток (MODE×width кросс-продукт, 24-file хвост) ограничен mirage-findings research-log и **не меняет стратегическое направление**: CM — рычаг при любом сценарии. Moonshot-предложение «реаудит безопаснее» отклонено: реаудит существующих схем доказанно даёт 0, а CM доказан byte-exact (+9% к ppmd на dickens) — риск в CM-throughput (IW-06), не в направлении.


---

## 10. Рекомендация оператору (финальное решение — за оператором)

**Развилка reset vs реаудит решается числом 0%: путь = RESET-LITE.**
1. **Заводить follow-up задачу: NEW-05 (BWT+CM) → NEW-01 (full CM) как `--value-scheme cm` за competitive-min rail.** Дешёвый slice-validated старт (NEW-05), затем top-rail (NEW-01). Регрессия невозможна (rail берёт min).
2. **Prerequisite: IW-06/FU-01 (throughput / u16→u32 block)** — CM на enwik8-scale требует block-parallel без 64KB-cliff (research-log пометил URGENT/gating).
3. **Параллельно: NEW-04 (узкий LZMA-специалист)** для tiny-SPARC sum — единственный класс, где CM проигрывает.
4. **Закрыть IW-02 как shipped** (mr/x-ray уже #1); поправить устаревшую _INDEX-таблицу.
5. **НЕ тратить усилий на:** реаудит диспетчера, tiny-dispatcher, per-arch BCJ-фильтры — измеренные mirages.
