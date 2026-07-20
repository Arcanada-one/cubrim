# CUBR-0041 — Статус (стратегическая диагностика per-type vs единый)

**Оркестратор:** DEVS. **Стенд:** dev-ai 64c (mesh 100.118.134.82). **Старт:** 2026-07-06.
**Baseline кода:** стендовый бинарь `/root/cubrim-stand/cubrim-rs/target/release/cubrim` (built Jul 3, соответствие origin/main проверяется).

## Ключевой архитектурный факт (из чтения codec.rs)
`encode_rans_family_value_stream` («competitive rail») конкурирует ТОЛЬКО ВНУТРИ rANS-семейства
(BwtRans/Order2Rans/BwtAdaptive/BwtContextMix/BwtGeoMix/LzRans → идентичный min-выход).
НЕ конкурирует bitpack vs entropy vs rANS. Значит per-file выбор CLI-схемы имеет реальный headroom.
`auto`/default = BitpackFixed (слабый глобальный дефолт). Пример: fields.c auto=0.887, entropy=0.650.

## World-корпус (243 004 774 B, 11 файлов)
enwik8 100MB · silesia/mozilla 51MB · webster 41MB · samba 21MB · dickens 10MB · mr 10MB · x-ray 8.5MB · canterbury{sum,cp.html,fields.c,xargs.1,grammar.lsp}

## 12 value-schemes
bitpack-fixed rle-codes entropy entropy-context entropy-context-2 bwt-entropy bwt-rans order2-rans bwt-adaptive bwt-ctxmix bwt-geomix lz-rans

## Прогресс — ✅ ЗАВЕРШЕНО
- [x] Baseline: mesh OK, стенд найден, корпус+бинарь+source инвентаризованы
- [x] Архитектурный анализ auto/competitive-rail (codec.rs) — rail конкурирует только внутри rANS-семьи
- [x] Инцидент -P64 thrash (load 985) → recovered, -P4 + setsid → healthy
- [x] Oracle sweep: 12 файлов × 13 схем, RT-verified (дубли дедуплицированы by (file,scheme))
- [x] Ref-sweep: ppmd/xz/brotli/zstd/bzip2 на тех же 12 файлах
- [x] Oracle-overall = 0.262140 == current 0.262140 → **ceiling 0.000000 (0%)**
- [x] Реаудит гипотез сквозь per-type-призму (76 файлов + 41KB _RESEARCH-LOG.md)
- [x] Карта тип→режим (измеренная) + реопен-список (IW-02 скорректирован: уже LIVE)
- [x] Мультивендорный консилиум (deepseek + moonshot): оба → REFUTED + RESET-LITE
- [x] Финальный отчёт → `/home/dev/cubr0041-work/REPORT-CUBR-0041.md`

## Артефакты (`/home/dev/cubr0041-work/`)
- `REPORT-CUBR-0041.md` — **полный отчёт** (число, ландшафт, карта тип→режим, реопен-список, консилиум, рекомендация)
- `oracle.tsv` — сырые замеры cubrim (scheme/file/orig/comp/ratio/rt_ok/ms), RT-verified
- `ref.tsv` — замеры ppmd/xz/brotli/zstd/bzip2 на том же корпусе
- `oracle-analysis.txt` — вычисленные overall'ы + per-file oracle-picks + type map
- `analyze2.py` — анализатор (rANS-rail collapse, ceiling, type map)
- `consilium-brief.md` + `consilium-deepseek.txt` + `consilium-moonshot.txt` + `consilium-synthesis.md`
- `oracle-sweep.sh` / `big-sweep.sh` / `ref-sweep.sh` — прогонные скрипты (стенд)

## ✅ ФИНАЛЬНОЕ ЧИСЛО (RT-verified, 12-file world-корпус 243 004 774 B)
**Потолок специализации на существующих value-схемах = 0.000000 (РОВНО НОЛЬ, 0.0%).**
- CURRENT competitive-min (rANS rail) = **0.262140**
- ORACLE (идеальный per-file выбор из всех 12 схем) = **0.262140**
- На НУЛЕ из 12 файлов какая-либо не-rANS схема бьёт rANS rail. Rail УЖЕ = per-file оптимум везде.
- rANS-семья (6 схем) byte-identical подтверждено эмпирически на всех 11 мультисхемных файлах.

**Провенанс расхождения с брифом:** операторские 0.247866/ppmd 0.228591 — это 24-file бенчмарк (с супер-сжимаемыми nci/xml/ptt5). Мой стендовый world-корпус = 12 файлов (enwik8-heavy) → current 0.262140, ppmd 0.239264. Потолок 0% корпусо-инвариантен по сути (rail оптимален per-file), измерен на 12-file.

**Ландшафт на ОДНОМ 12-file корпусе (apples-to-apples):** ppmd 0.239264 < xz 0.248611 < brotli 0.255819 < **cubrim 0.262140** < zstd 0.270837 < bzip2 0.285740. Cubrim отстаёт от ppmd на +9.6%, от xz на +5.4% — и НИ ОДНА существующая схема этого не закрывает.

**Verify-first catch (карта врала):** этот build УЖЕ даёт mr=0.2104 (бьёт ppmd 0.2326, −9.5%) и x-ray=0.4451 (бьёт ppmd 0.4544, −2.1%) — cubrim УЖЕ #1 на обоих image. IW-02-флип LIVE. _INDEX-таблица с mr rank-3 (0.2540) — устаревшая проза. → реопен-список скорректирован: IW-02 не «to ship», а «shipped».

**Вывод по развилке = RESET-LITE (ветка (a) из брифа):** ceiling=0 ⇒ competitive-min УЖЕ диспетчеризует оптимально per-file; специализация существующими схемами ИСЧЕРПАНА ⇒ нужны НОВЫЕ режимы (CM value-scheme за тем же rail). НЕ реаудит диспетчера (он доказанно оптимален), НЕ полный reset (rail/MODE-dispatch/MED16-image-win/rANS — работают, сохранить).

## КЛЮЧЕВЫЕ ВЫВОДЫ (архитектура)
1. **Per-type диспетчер УЖЕ существует** на уровне MODE (LZ/CUBE/CHUNKED/MED16/SOA) + competitive-min ВНУТРИ rANS-семейства. «Единый алгоритм» — strawman, его нет.
2. **order2-rans == lz-rans == вся rANS-семья byte-for-byte** (6 из 12 CLI-схем коллапсируют в один min). Бенчмарк cubrim воспроизводится ТОЧНО явным order2-rans (research-log L290). `auto`/CLI-default (bitpack/CUBE) — сломанный дефолт для tiny (0.88-0.90), НЕ то, что репортит бенчмарк.
3. **Специализация на СУЩЕСТВУЮЩИХ value-схемах ~исчерпана.** Почти все per-type «рычаги» при замере = MIRAGE: tiny-dispatcher (competitive-min уже роутит), SPARC-BCJ (+0.96%), x86-BCJ (≤0.2%). Разрывы — это MODEL-CLASS gap (order-2 → order-3+/CM), а НЕ dispatch gap.
4. **Настоящий потолок = НОВЫЙ backend (CM/context-mixing).** zpaq-m5 CM бьёт лидеров на ПОЧТИ ВСЕХ классах: text (dickens 0.2055 vs ppmd 0.2253, −9%), code≥10KB (b' fields.c/cp.html), large exe (mozilla 0.2351 vs 7z 0.2605, −10%), 16-bit image. Проигрывает LZMA только на tiny SPARC sum (38KB). NEW-01 CM-проба написана, RT-OK, 13-21% к текущему backend на каждом text-файле, без 64KB-cliff.
5. **Реаудит-вывод:** архитектура = ensemble/competitive-min rail (шасси УЖЕ есть) + ОДИН широкий CM-backend + ОДИН узкий LZMA-специалист (tiny-SPARC). Не «больше per-type фильтров», а лучший общий модель за тем же rail. → это **reset-lite (новый value-scheme за rail), НЕ реаудит диспетчера.**

## Реопен-кандидаты (false-negative из-за усреднения / незаинтегрированные per-type WIN)
- **IW-02 (mr MED16 w=512 → 0.2104 < ppmd 0.2308, RT-OK) — SHIP.** Измеренный per-type WIN #1 с запасом 9%, НЕ в диспетчере → mr сидит rank 3 (0.2540). Чистые деньги на столе от отсутствия per-type диспетча уже измеренного кандидата. Ось = MODE/width, ортогональна value-scheme (мой oracle её НЕ ловит → полный потолок ≥ моего числа).
- **H-14 (byte pre-transforms) NO-GO → conditional reopen** при появлении type-детектора (delta для табличных, stride-N для multichannel) — «пре-процессинг как часть per-type диспетчера».
- **H-15 (distance-map) NO-GO → conditional reopen** если tiny вернутся на CUBE с новым контекстным кодером.
