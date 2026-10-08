// 🧾 ԱԿՏ՝ ներկառուցված տեխ. մոնիտորինգից, մեդիա պլանից կամ Excel/CSV ֆայլից -> Word/PDF + տպել
// Հաշվարկը՝ ԸՍՏ ԺԱՄԵՐԻ. ո՞ր հասցեում, ո՞ր օրը, ո՞ր ժամերին էր գովազդն անջատված
import { S, api, clear, clientSelect, field, filesResult, h, loader, monthRange,
  nf, photoButton, table, toIso, toast, t } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Отчёт о выходах: план / факт / отключения по часам'
  : 'Հեռարձակման հաշվետվություն՝ պլան / փաստ / անջատումներ ըստ ժամերի';

/* ժամեր՝ [10, 11, 12, 15] -> «10:00–13:00, 15:00–16:00» */
const hh = x => String(x).padStart(2, '0') + ':00';
const hOrder = x => (x < 5 ? x + 24 : x);
export function hourRanges(hours) {
  const hs = [...new Set((hours || []).map(Number))].sort((a, b) => hOrder(a) - hOrder(b));
  const out = [];
  for (let i = 0; i < hs.length;) {
    let j = i;
    while (j + 1 < hs.length && hOrder(hs[j + 1]) - hOrder(hs[j]) === 1) j++;
    out.push(`${hh(hs[i])}–${hh((hs[j] + 1) % 24)}`);
    i = j + 1;
  }
  return out.join(', ');
}
/* անջատումները՝ ամեն օրը առանձին տողով՝ [N, հասցե, ամսաթիվ, ժամեր, չհեռ.] (հասցեն՝ միայն առաջին տողում) */
function offRows(byAddr, L) {
  const out = [];
  let n = 0;
  (byAddr || []).filter(a => a.off_hours).forEach(a => {
    n += 1;
    const list = (a.off_list || []).filter(r => (r.hours || []).length || r.full);
    const perH = a.off_hours ? (a.missed || 0) / a.off_hours : 2;
    if (!list.length) { out.push({ cls: n % 2 ? '' : 'zebra', cells: [n, a.addr, '', a.off_detail || '', nf(a.missed)] }); return; }
    list.forEach((r, i) => {
      const hrs = hourRanges(r.hours);
      const txt = r.full ? `${L ? 'весь день' : 'ամբողջ օրը'}${hrs ? ` (${hrs})` : ''}` : hrs;
      out.push({ cls: n % 2 ? '' : 'zebra', cells: [i ? '' : n, i ? '' : h('b', { text: a.addr }), r.date, txt,
        nf(r.missed || Math.round(perH * (r.hours || []).length))] });
    });
  });
  return out;
}

const A = { client: '', contract: '', start: '', end: '', source: 'plan', token: null, files: [],
  link: '', planned: 0, times: [], perHour: 2, addrMode: 'all', targets: [], nets: [], preview: null, plan: null, ui: null,
  logos: [], logoNet: '', logoManual: false, seal: true };

export async function render() {
  const L = S.lang === 'ru' ? 1 : 0;
  if (!A.start) { const [a, b] = monthRange(1); A.start = a; A.end = b; }
  const root = h('div');
  const previewBox = h('div');
  const sourceBox = h('div');

  // --- 1. հիմնական տվյալներ
  const { wrap, input } = clientSelect(A.client);
  input.addEventListener('input', () => { A.client = input.value; });
  const contract = h('input', { type: 'text', value: A.contract, placeholder: '0056' });
  contract.addEventListener('input', () => { A.contract = contract.value; });
  const s = h('input', { type: 'date', value: A.start });
  const e = h('input', { type: 'date', value: A.end });
  s.addEventListener('change', () => { A.start = s.value; A.reloadMonths?.(); });
  e.addEventListener('change', () => { A.end = e.value; A.reloadMonths?.(); });
  const quick = h('button', { class: 'btn sm' }, L ? 'Прошлый месяц' : 'Անցած ամիս');
  quick.addEventListener('click', () => { const [a, b] = monthRange(1); s.value = A.start = a; e.value = A.end = b; A.reloadMonths?.(); });
  // PDF-ի աջ վերևի խանութի լոգո + ստորագրություն/կնիք
  const logoSel = h('select', {}, h('option', { value: '' }, L ? '— без логотипа —' : '— առանց լոգոյի —'));
  const logoPrev = h('img', { alt: '', style: 'height:34px;max-width:120px;object-fit:contain;display:none' });
  const drawLogo = () => {
    logoSel.value = A.logoNet;
    const n = A.logos.find(x => String(x.index) === String(A.logoNet));
    logoPrev.style.display = n ? '' : 'none';
    if (n) logoPrev.src = n.logo;
  };
  const loadLogos = async () => {
    try { A.logos = (await api('/api/act/logos?client=' + encodeURIComponent(A.client), { quiet: true })).networks; } catch (e) { return; }
    A.logos.forEach(n => logoSel.append(h('option', { value: String(n.index) }, n.short)));
    drawLogo();
  };
  logoSel.addEventListener('change', () => { A.logoNet = logoSel.value; A.logoManual = true; drawLogo(); });
  const seal = h('input', { type: 'checkbox', checked: A.seal });
  seal.addEventListener('change', () => { A.seal = seal.checked; });
  A.ui = { client: input, s, e, drawLogo, logoSel };   // մեդիա պլանի բեռնումը լրացնում է այս դաշտերը
  if (!A.logos.length) loadLogos(); else { A.logos.forEach(n => logoSel.append(h('option', { value: String(n.index) }, n.short))); drawLogo(); }

  // 📷 լուսանկար/ֆայլ (պայմանագիր, մեդիա պլան, նամակ) -> պատվիրատու, պայմանագիր, ժամանակահատված, հասցեներ
  const photo = photoButton({
    section: 'Broadcast ACT (report of audio ads played in shops)', match: 'addresses', cls: 'btn primary',
    note: 'Usually a photo of the contract or media plan for this customer.',
    fields: [
      { key: 'client', label: 'Customer (client) company name' },
      { key: 'contract', label: 'Contract number', hint: 'e.g. 0056' },
      { key: 'start', type: 'date', label: 'Reporting / broadcast period start date' },
      { key: 'end', type: 'date', label: 'Reporting / broadcast period end date' },
      { key: 'times', label: 'Broadcast schedule', hint: "a range like '9:20-23:50/30' or a list like '9:00, 13:00'" },
      { key: 'addresses', type: 'list', label: 'Shop addresses where the ad plays (one per item)' },
    ],
    onResult: (res, file) => {
      const v = res.values || {};
      if (v.client) { A.client = v.client; input.value = v.client; }
      if (v.contract) { A.contract = v.contract; contract.value = v.contract; }
      if (toIso(v.start)) { A.start = toIso(v.start); s.value = A.start; }
      if (toIso(v.end)) { A.end = toIso(v.end); e.value = A.end; }
      if (res.slots?.length) A.times = res.slots;
      const addrs = [...(res.matched || []).map(m => ({ net: m.net_name, addr: m.address })),
        ...(res.unmatched || []).map(a => ({ net: '', addr: a }))];
      if (addrs.length) {
        A.plan = { client: A.client, start: toIso(v.start) || '', end: toIso(v.end) || '', slots: res.slots || [], addresses: addrs,
          file: '📷 ' + file.name, warnings: res.unmatched?.length
            ? [`${L ? 'Не найдены в сетях' : 'Ցանցերում չգտնվեցին'}: ${res.unmatched.length}`] : [] };
        A.source = 'plan';
      }
      A.preview = null; clear(previewBox); drawTabs(); drawSource();
    } });

  root.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' }, h('h2', { text: '🧾 ' + (L ? 'Данные акта' : 'ԱԿՏ-ի տվյալները') }),
      h('div', { class: 'right' }, photo)),
    h('div', { class: 'gradline' }),
    h('div', { class: 'grid c2' },
      field(t('word.client'), wrap),
      field(L ? 'Номер договора' : 'Պայմանագրի համարը', contract)),
    h('div', { class: 'grid c2' }, field(t('word.start'), s), field(t('word.end'), e)),
    h('div', { class: 'grid c2' },
      field(L ? 'Логотип магазина (справа вверху в PDF)' : 'Խանութի լոգո (PDF-ի աջ վերևում)',
        h('div', { class: 'inline' }, logoSel, logoPrev),
        { hint: L ? 'Подбирается автоматически по адресам/клиенту — можно поменять' : 'Ընտրվում է ավտոմատ՝ հասցեներով/պատվիրատուով, կարելի է փոխել' }),
      field(L ? 'Подпись и печать' : 'Ստորագրություն և կնիք',
        h('label', { class: 'check' }, seal, L ? 'Поставить подпись и печать Mix Media' : 'Դնել Mix Media-ի ստորագրությունը և կնիքը'),
        { hint: L ? 'Место для печати заказчика остаётся пустым' : 'Պատվիրատուի կնիքի տեղը մնում է դատարկ' })),
    h('div', { class: 'row' }, quick)));

  // --- 2. աղբյուր
  const tabs = h('div', { class: 'grid', style: 'grid-template-columns:repeat(auto-fit,minmax(215px,1fr))' });
  const SRC = [
    ['plan', '📋', L ? 'Файл медиаплана' : 'Մեդիա պլանի ֆայլ', L ? 'Адреса из медиаплана + отключения по часам' : 'Հասցեներ մեդիա պլանից + անջատումներ ժամերով'],
    ['monitor', '📡', L ? 'Тех. мониторинг' : 'Տեխ. մոնիտորինգ', L ? 'Данные из раздела «Тех. мониторинг»' : 'Տվյալները «Տեխ. մոնիտորինգ» բաժնից'],
    ['file', '📎', L ? 'Файл xlsx / csv' : 'Ֆայլ xlsx / csv', L ? 'Загрузить с компьютера' : 'Բեռնել համակարգչից'],
  ];
  const drawTabs = () => {
    clear(tabs);
    SRC.forEach(([id, ic, title, note]) => tabs.append(h('button', {
      class: 'pick' + (A.source === id ? ' sel' : ''),
      onClick: () => { A.source = id; A.preview = null; clear(previewBox); drawTabs(); drawSource(); },
    }, h('div', { class: 'pico' }, ic), h('div', {}, h('div', { class: 'pt', text: title }), h('div', { class: 'pd', text: note })))));
  };
  root.append(h('div', { class: 'card' },
    h('h2', { text: '📥 ' + (L ? 'Источник данных' : 'Տվյալների աղբյուրը') }),
    h('p', { class: 'small muted', text: L ? 'Данные только читаются, ничего не изменяется.'
      : 'Տվյալները միայն կարդացվում են, ոչինչ չի փոխվում:' }),
    tabs, h('div', { class: 'hr' }), sourceBox));
  root.append(previewBox);
  drawTabs();
  drawSource();

  function drawSource() {
    clear(sourceBox);
    if (A.source === 'plan') sourceBox.append(planSource(L, show));
    else if (A.source === 'file') sourceBox.append(fileSource(L, show));
    else sourceBox.append(monitorSource(L, show));
  }
  function show(res) {
    A.preview = res;
    // ժամանակահատվածը սեղմվել է մեդիա պլանի օրերով՝ ԱԿՏ-ը ստեղծվում է նույն ժամանակահատվածով
    if (res.start && res.end && (res.start !== A.start || res.end !== A.end)) {
      A.start = res.start; A.end = res.end; s.value = A.start; e.value = A.end;
    }
    if (!A.logoManual && res.net_guess !== null && res.net_guess !== undefined) { A.logoNet = String(res.net_guess); A.ui?.drawLogo(); }
    clear(previewBox).append(previewCard(res, L, show));
    previewBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  // ✏️ պահված ԱԿՏ՝ նույն տվյալներով (վերնագիր, լոգո, կնիք) և նախորդ հաշվարկով
  if (S.prefill?.section === 'act') {
    const { data = {}, result } = S.prefill;
    S.prefill = null;
    if (data.client) { A.client = data.client; input.value = data.client; }
    if (data.contract) { A.contract = data.contract; contract.value = data.contract; }
    if (toIso(data.start)) { A.start = toIso(data.start); s.value = A.start; }
    if (toIso(data.end)) { A.end = toIso(data.end); e.value = A.end; }
    if (data.logo_net !== null && data.logo_net !== undefined) { A.logoNet = String(data.logo_net); A.logoManual = true; drawLogo(); }
    if (data.seal === false) { A.seal = false; seal.checked = false; }
    if (result?.days?.length) {
      const sum = k => result.days.reduce((a, d) => a + (Number(d[k]) || 0), 0);
      const planned = sum('planned'), played = sum('played');
      show({ ...result, planned, played, missed: Math.max(planned - played, 0),
        pct: planned ? Math.round(1000 * played / planned) / 10 : null,
        off_hours: (result.by_addr || []).reduce((a, r) => a + (Number(r.off_hours) || 0), 0), restored: true });
    }
    toast(L ? 'АКТ открыт: можно поменять данные и создать заново' : 'ԱԿՏ-ը բացվեց՝ կարելի է փոխել տվյալները և ստեղծել նորից');
  }
  return root;
}

/* ------------------------------------------------ աղբյուրները */
function plannedField(L) {
  const inp = h('input', { type: 'number', min: '0', value: A.planned });
  inp.addEventListener('input', () => { A.planned = Number(inp.value) || 0; });
  return field(L ? 'План выходов в день (все адреса)' : 'Օրական նախատեսված հեռարձակում (բոլոր հասցեներով)', inp,
    { hint: L ? 'Например: 30 выходов × 23 адреса = 690. Если в файле есть колонка «План» — оставьте 0.'
      : 'Օրինակ՝ 30 հեռարձակում × 23 հասցե = 690: Եթե ֆայլում «Նախատեսված» սյունակ կա՝ թողեք 0:' });
}

function fileSource(L, show) {
  const box = h('div');
  const inp = h('input', { type: 'file', accept: '.xlsx,.xlsm,.csv', multiple: true, style: 'display:none' });
  const zone = h('div', { class: 'dropzone' }, h('div', { class: 'dzi' }, '📎'),
    h('div', { text: L ? 'Нажмите или перетащите .xlsx / .csv' : 'Սեղմեք կամ քաշեք .xlsx / .csv ֆայլը' }),
    h('div', { class: 'tiny muted', id: 'act-files', text: A.files.join(', ') }));
  const upload = async fileList => {
    const fd = new FormData();
    [...fileList].forEach(f => fd.append('files', f));
    loader(true, L ? 'Читаю файл…' : 'Կարդում եմ ֆայլը…');
    try {
      const r = await api('/api/act/upload', { method: 'POST', form: fd });
      A.token = r.token; A.files = r.files;
      zone.lastChild.textContent = r.files.join(', ');
      toast(`✅ ${r.files.length} ${t('word.files').toLowerCase()}`);
      await preview();
    } finally { loader(false); }
  };
  zone.addEventListener('click', () => inp.click());
  zone.addEventListener('dragover', ev => { ev.preventDefault(); zone.classList.add('over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('over'));
  zone.addEventListener('drop', ev => { ev.preventDefault(); zone.classList.remove('over'); if (ev.dataTransfer.files.length) upload(ev.dataTransfer.files); });
  inp.addEventListener('change', () => { if (inp.files.length) upload(inp.files); });
  const btn = h('button', { class: 'btn primary' }, '🔍 ' + (L ? 'Посчитать' : 'Հաշվել'));
  btn.addEventListener('click', preview);
  async function preview() {
    if (!A.token) { toast(L ? 'Сначала загрузите файл' : 'Նախ բեռնեք ֆայլը', 'err'); return; }
    if (!check(L)) return;
    loader(true);
    try {
      const res = await api('/api/act/preview', { method: 'POST', body: {
        source: 'file', token: A.token, client: A.client, start: A.start, end: A.end, planned_per_day: A.planned } });
      show(res);
    } catch (e) { /* toast */ } finally { loader(false); }
  }
  box.append(zone, inp, h('div', { style: 'margin-top:12px' }, plannedField(L)), h('div', { class: 'row' }, btn));
  return box;
}

/* ժամերի ընտրություն (եթերացանկ)՝ ընդհանուր մոնիտորինգի և մեդիա պլանի աղբյուրների համար.
   fromPlan()՝ true, երբ բոլոր հասցեները մեդիա պլանից ունեն իրենց ժամերը (այդ դեպքում ընտրությունը թաքցվում է) */
function timesBlock(L, fromPlan = () => false) {
  const timesInfo = h('span', { class: 'badge warn', text: '0' });
  const custom = h('input', { type: 'text', placeholder: '9:20-23:50/30' });
  const presets = h('div', { class: 'row' });
  const planNote = h('div', { class: 'small muted', style: 'display:none', text: L
    ? 'Часы берутся из медиаплана (у каждой сети — свои). План выходов = ровно как в медиаплане.'
    : 'Ժամերը վերցվում են մեդիա պլանից (ամեն ցանցի համար՝ իրը): Նախատեսվածը՝ ճիշտ մեդիա պլանի պես:' });
  const perDay = () => new Set(A.times).size;    // ճիշտ այնքան սփոթ, որքան եթերացանկում է
  const perHour = h('input', { type: 'number', min: '1', max: '12', value: String(A.perHour), style: 'width:80px' });
  perHour.addEventListener('input', () => { A.perHour = Math.max(1, Math.min(12, Number(perHour.value) || 2)); refresh(); });
  const perHint = h('span', { class: 'tiny muted' });
  const refresh = () => {
    perHint.textContent = L ? `1 час отключения = не меньше ${A.perHour} не вышедших (если в часе больше выходов — по медиаплану)`
      : `Անջատված 1 ժամ = առնվազն ${A.perHour} չհեռարձակված (ժամում ավելի շատ սփոթ կա՝ ըստ մեդիա պլանի)`;
    const plan = fromPlan();
    presets.style.display = plan ? 'none' : '';
    planNote.style.display = plan ? '' : 'none';
    const n = perDay();
    timesInfo.textContent = plan ? (L ? 'из медиаплана' : 'մեդիա պլանից')
      : A.times.length ? `${n} ${L ? 'выходов/день' : 'հեռարձակում/օր'}` : '0';
    timesInfo.className = 'badge ' + (plan || A.times.length ? 'ok' : 'warn');
  };
  const setTimes = async text => {
    try {
      const r = await api('/api/plan/times', { method: 'POST', body: { text }, quiet: true });
      A.times = r.slots;
      refresh();
    } catch (e) { toast(e.message, 'err'); }
  };
  (S.meta.presets || []).forEach(p => presets.append(h('button', { class: 'btn sm', onClick: () => setTimes(p) },
    p.replace('/', ' · '))));
  presets.append(h('div', { class: 'inline', style: 'flex:1;min-width:200px' }, custom,
    h('button', { class: 'btn sm', onClick: () => setTimes(custom.value) }, t('btn.save'))));
  refresh();
  const node = h('div', {}, h('div', { class: 'card-head' },
    h('h3', { text: '🕒 ' + (L ? 'График выходов' : 'Եթերացանկ') }), h('div', { class: 'right' }, timesInfo)), planNote, presets,
    h('div', { class: 'row', style: 'margin-top:10px' },
      h('span', { class: 'small', text: L ? 'Выходов в 1 часе (минимум):' : 'Սփոթ 1 ժամում (նվազագույնը)՝' }), perHour, perHint));
  return { node, refresh };
}

/* ընտրված ամիսների տվյալները՝ ներկառուցված «Տեխ. մոնիտորինգ» բաժնից (Drive պետք չէ) */
function monthsBlock(L) {
  const monthsBox = h('div', { style: 'margin-bottom:12px' });
  const load = async () => {
    if (!A.start || !A.end) return;
    clear(monthsBox);
    let r;
    try { r = await api(`/api/act/monitor/months?start=${A.start}&end=${A.end}`, { quiet: true }); } catch (e) { return; }
    monthsBox.append(h('div', { class: 'card-head', style: 'margin-bottom:8px' },
      h('h3', { text: '📡 ' + (L ? 'Тех. мониторинг (встроенный)' : 'Տեխ. մոնիտորինգ (ներկառուցված)') }),
      h('div', { class: 'right' },
        h('button', { class: 'btn sm', onClick: () => { location.hash = '#/techmon'; } }, '↗ ' + (L ? 'Открыть раздел' : 'Բացել բաժինը')))));
    if (r.months.some(m => !m.ready)) {
      monthsBox.append(h('p', { class: 'small', style: 'color:var(--warn)', text: L
        ? 'Для некоторых месяцев данных нет. Старые файлы можно перенести в разделе «Тех. мониторинг» → «Настройки и импорт».'
        : 'Որոշ ամիսների տվյալներ չկան: Հին ֆայլերը կարելի է տեղափոխել «Տեխ. մոնիտորինգ» → «Կարգավորումներ և ներմուծում» բաժնում:' }));
    }
    const list = h('div', { class: 'list' });
    r.months.forEach(m => list.append(h('div', { class: 'li' },
      h('span', { class: 'badge ' + (m.ready ? 'ok' : 'err'), text: m.month }),
      h('div', { class: 't' }, h('div', { class: 's', text: m.ready
        ? `✓ ${L ? 'дней с данными' : 'օր տվյալներով'}: ${m.days} · ${L ? 'отметок' : 'նշում'}: ${m.events}`
        : (L ? 'данных за этот месяц нет' : 'այս ամսվա տվյալներ չկան') })))));
    monthsBox.append(list);
  };
  load();
  A.reloadMonths = load;     // ամսաթվերը փոխելիս ամիսների ցուցակը թարմանում է
  return { node: monthsBox, reload: load };
}

/* 📋 Մեդիա պլանի ֆայլ -> հասցեներ + ժամանակահատված + ժամեր -> մոնիտորինգով՝ ով, երբ է անջատված */
function planSource(L, show) {
  const box = h('div');
  const infoBox = h('div', { style: 'margin:12px 0' });
  const inp = h('input', { type: 'file', accept: '.pdf,.xlsx,.xlsm,.csv,.docx', style: 'display:none' });
  const zone = h('div', { class: 'dropzone' }, h('div', { class: 'dzi' }, '📋'),
    h('div', { text: L ? 'Нажмите или перетащите файл медиаплана (.pdf, .xlsx, .csv, .docx)'
      : 'Սեղմեք կամ քաշեք մեդիա պլանի ֆայլը (.pdf, .xlsx, .csv, .docx)' }),
    h('div', { class: 'tiny muted', text: A.plan ? A.plan.file : '' }));
  const months = monthsBlock(L);
  // բոլոր հասցեները մեդիա պլանից ունեն իրենց ժամերը՝ հաշվում ենք ՄԻԱՅՆ դրանցով
  const planHours = () => !!A.plan?.addresses?.length && A.plan.addresses.every(a => a.slots?.length);
  const times = timesBlock(L, planHours);

  const drawInfo = () => {
    clear(infoBox);
    const p = A.plan;
    if (!p) return;
    const perAddr = p.per_day || new Set(p.slots).size;
    infoBox.append(h('div', { class: 'grid c4' },
      tile(L ? 'Клиент' : 'Պատվիրատու', p.client || '—'),
      tile(L ? 'Период' : 'Ժամանակահատված', p.start ? `${p.start.split('-').reverse().join('.')} – ${p.end.split('-').reverse().join('.')}` : '—'),
      tile(L ? 'Адресов' : 'Հասցե', String(p.addresses.length)),
      tile(L ? 'Выходов в день' : 'Հեռարձակում/օր', !p.slots.length ? '—' : p.per_day_total
        ? `${nf(p.per_day_total)} (${perAddr} / ${L ? 'адрес' : 'հասցե'})` : String(perAddr))));
    if (p.nets?.length) infoBox.append(h('div', { class: 'small muted', style: 'margin-top:8px',
      text: `🏪 ${L ? 'Сети' : 'Ցանցեր'}: ${p.nets.join(' · ')}` }));
    if (p.clips?.length) infoBox.append(h('div', { class: 'small muted', style: 'margin-top:4px',
      text: `🎵 ${L ? 'Ролики' : 'Հոլովակներ'}: ${p.clips.map(c => `${c.n}. ${c.name}`).join(' · ')}` }));
    if (p.schedules?.length) infoBox.append(h('div', { class: 'small', style: 'margin-top:8px' },
      h('b', { text: '🕒 ' + (L ? 'График из медиаплана (у каждой группы свой):' : 'Եթերացանկը մեդիա պլանից (ամեն խմբի համար՝ իրը)՝') }),
      h('ul', { style: 'margin:4px 0 0;padding-left:20px' }, ...p.schedules.map(s => h('li', {
        text: `${s.nets.join(', ')} · ${s.count} ${L ? 'адр.' : 'հասցե'} — ${s.slots.length} ${L ? 'выходов/день' : 'սփոթ/օր'}`
          + ` (${s.slots[0]}–${s.slots[s.slots.length - 1]})` }))),
      h('div', { class: 'tiny muted', text: L ? 'АКТ считается ровно по этим часам: план = выходы медиаплана × адреса × дни, не вышло = выходы в часы отключения.'
        : 'ԱԿՏ-ը հաշվվում է ճիշտ այս ժամերով՝ նախատեսված = մեդիա պլանի սփոթներ × հասցեներ × օրեր, չհեռարձակված = անջատված ժամերի սփոթները:' })));
    (p.warnings || []).forEach(w => infoBox.append(h('div', { class: 'small', style: 'color:var(--warn);margin-top:8px', text: '⚠️ ' + w })));
    if (!p.slots.length) infoBox.append(h('div', { class: 'small', style: 'color:var(--warn);margin-top:8px',
      text: '⚠️ ' + (L ? 'В файле нет графика выходов — выберите время ниже.' : 'Ֆայլում եթերացանկ չկա՝ ընտրեք ժամերը ստորև:') }));
    const list = h('div', { class: 'list scroll sm', style: 'margin-top:10px' });
    p.addresses.forEach((a, i) => list.append(h('div', { class: 'li' }, h('span', { class: 'badge', text: String(i + 1) }),
      h('div', { class: 't' }, h('b', { text: a.addr }), a.net ? h('div', { class: 's', text: a.net }) : null))));
    infoBox.append(h('details', {}, h('summary', { class: 'small', text: L ? 'Показать адреса' : 'Ցույց տալ հասցեները' }), list));
  };

  const upload = async f => {
    const fd = new FormData();
    fd.append('file', f);
    loader(true, L ? 'Читаю медиаплан…' : 'Կարդում եմ մեդիա պլանը…');
    let r;
    try {
      r = await api('/api/act/mediaplan', { method: 'POST', form: fd });
    } catch (e) { loader(false); return; /* toast-ը ցույց է տրվել */ }
    loader(false);
    A.plan = r;
    zone.lastChild.textContent = r.file || '';
    // մեդիա պլանի բոլոր տվյալները՝ ԱԿՏ-ի դաշտերում (պատվիրատու, ժամկետ, ժամեր, խանութի լոգո)
    const fill = (el, v) => { if (!el) return; el.value = v; el.classList.add('filled'); setTimeout(() => el.classList.remove('filled'), 4000); };
    if (r.client) { A.client = r.client; fill(A.ui?.client, r.client); }
    if (r.start && r.end) { A.start = r.start; A.end = r.end; fill(A.ui?.s, r.start); fill(A.ui?.e, r.end); }
    A.times = r.slots.length ? r.slots : A.times;
    if (!A.logoManual && r.net_guess !== null && r.net_guess !== undefined) { A.logoNet = String(r.net_guess); A.ui?.drawLogo(); }
    times.refresh();
    months.reload();
    drawInfo();
    toast(`✅ ${L ? 'Медиаплан прочитан' : 'Մեդիա պլանը կարդացվեց'}: ${r.addresses.length} ${L ? 'адресов' : 'հասցե'}`);
    if (r.addresses.length && (planHours() || A.times.length) && A.client && A.start && A.end) await calc();   // միանգամից հաշվում ենք
  };
  zone.addEventListener('click', () => inp.click());
  zone.addEventListener('dragover', ev => { ev.preventDefault(); zone.classList.add('over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('over'));
  zone.addEventListener('drop', ev => { ev.preventDefault(); zone.classList.remove('over'); if (ev.dataTransfer.files.length) upload(ev.dataTransfer.files[0]); });
  inp.addEventListener('change', () => { if (inp.files.length) upload(inp.files[0]); });

  const btn = h('button', { class: 'btn primary' }, '📋 ' + (L ? 'Посчитать отключения по адресам' : 'Հաշվել անջատումները ըստ հասցեների'));
  async function calc() {
    if (!A.plan?.addresses.length) { toast(L ? 'Сначала загрузите медиаплан' : 'Նախ բեռնեք մեդիա պլանը', 'err'); return; }
    if (!check(L)) return;
    if (!planHours() && !A.times.length) { toast(L ? 'Выберите часы' : 'Ընտրեք ժամերը', 'err'); return; }
    loader(true, L ? 'Читаю мониторинг…' : 'Կարդում եմ մոնիտորինգը…');
    try {
      const res = await api('/api/act/monitor/preview', { method: 'POST', body: {
        client: A.client, start: A.start, end: A.end, times: A.times, per_hour: A.perHour, addr_mode: 'txt',
        targets: A.plan.addresses, plan_start: A.plan.start || '', plan_end: A.plan.end || '' } });
      show(res);
    } catch (e) { /* toast */ } finally { loader(false); }
  }
  btn.addEventListener('click', calc);
  drawInfo();
  box.append(zone, inp, infoBox, months.node, times.node, h('div', { class: 'hr' }),
    h('div', { class: 'row', style: 'margin-top:12px' }, btn),
    h('p', { class: 'tiny muted', text: L ? 'Адреса из медиаплана сверяются с тех. мониторингом: по каждому адресу — в какие дни и часы реклама не выходила.'
      : 'Մեդիա պլանի հասցեները համեմատվում են տեխ. մոնիտորինգի հետ՝ ամեն հասցեով ո՞ր օրերին և ժամերին գովազդը չի հեռարձակվել:' }));
  return box;
}

function monitorSource(L, show) {
  const box = h('div');
  const months = monthsBlock(L);
  const monthsBox = months.node;
  const times = timesBlock(L);

  // հասցեների ռեժիմ
  const modeBox = h('div', { class: 'grid c3' });
  const targetsArea = h('textarea', { rows: '5', placeholder: L ? 'Один адрес на строку' : 'Յուրաքանչյուր հասցեն նոր տողից',
    value: A.targets.join('\n') });
  const netsBox = h('div', { class: 'list scroll sm' });
  const extra = h('div', { style: 'margin-top:10px' });
  const MODES = [['all', '📍', L ? 'Все адреса (все сети)' : 'Բոլոր հասցեները (բոլոր ցանցերը)'],
    ['net', '🏪', L ? 'По сетям' : 'Ըստ ցանցերի'],
    ['txt', '✍️', L ? 'Список адресов' : 'Հասցեների ցուցակ']];
  const drawMode = () => {
    clear(modeBox);
    MODES.forEach(([id, ic, title]) => modeBox.append(h('button', {
      class: 'pick' + (A.addrMode === id ? ' sel' : ''), onClick: () => { A.addrMode = id; drawMode(); },
    }, h('div', { class: 'pico' }, ic), h('div', {}, h('div', { class: 'pt', text: title })))));
    clear(extra);
    if (A.addrMode === 'txt') extra.append(field(t('word.addresses'), targetsArea));
    if (A.addrMode === 'net') {
      clear(netsBox);
      (S.meta.networks || []).forEach((n, i) => {
        const cb = h('input', { type: 'checkbox', checked: A.nets.includes(i) });
        cb.addEventListener('change', () => {
          A.nets = cb.checked ? [...A.nets, i] : A.nets.filter(x => x !== i);
        });
        netsBox.append(h('label', { class: 'li' }, cb,
          h('div', { class: 't' }, h('b', { text: n.name }), h('div', { class: 's', text: `${n.count} ${L ? 'адресов' : 'հասցե'}` }))));
      });
      extra.append(netsBox);
    }
  };
  drawMode();

  const btn = h('button', { class: 'btn primary' }, '📡 ' + (L ? 'Посчитать по мониторингу' : 'Հաշվել մոնիտորինգով'));
  btn.addEventListener('click', async () => {
    if (!check(L)) return;
    if (!A.times.length) { toast(L ? 'Выберите часы' : 'Ընտրեք ժամերը', 'err'); return; }
    A.targets = targetsArea.value.split(/[\r\n]+/).map(x => x.trim()).filter(Boolean);
    loader(true, L ? 'Читаю мониторинг…' : 'Կարդում եմ մոնիտորինգը…');
    try {
      const res = await api('/api/act/monitor/preview', { method: 'POST', body: {
        client: A.client, start: A.start, end: A.end, times: A.times, per_hour: A.perHour, addr_mode: A.addrMode,
        targets: A.targets, nets: A.nets } });
      show(res);
    } catch (e) { /* toast */ } finally { loader(false); }
  });
  box.append(monthsBox, times.node, h('div', { class: 'hr' }),
  h('h3', { text: '📍 ' + (L ? 'По каким адресам считать' : 'Ո՞ր հասցեներով հաշվել') }), modeBox, extra,
  h('div', { class: 'row', style: 'margin-top:12px' }, btn));
  return box;
}

function check(L) {
  if (!A.client.trim()) { toast(L ? 'Укажите клиента' : 'Լրացրեք հաճախորդը', 'err'); return false; }
  if (!A.start || !A.end || new Date(A.end) < new Date(A.start)) {
    toast(L ? 'Проверьте период' : 'Ստուգեք ժամանակահատվածը', 'err'); return false;
  }
  return true;
}

/* ------------------------------------------------ նախադիտում + ստեղծում */
function previewCard(res, L, show) {
  const card = h('div', { class: 'card' });
  const pct = res.pct === null || res.pct === undefined ? '—' : res.pct + '%';
  card.append(h('div', { class: 'card-head' },
    h('h2', { text: '📊 ' + (L ? 'Результат расчёта' : 'Հաշվարկի արդյունքը') }),
    h('div', { class: 'right' },
      h('button', { class: 'btn sm', onClick: () => printTable(res, L) }, '🖨 ' + t('btn.print')))));
  card.append(h('div', { class: 'grid c5' },
    tile(L ? 'План, выходов' : 'Նախատեսված', nf(res.planned)),
    tile(L ? 'Вышло' : 'Հեռարձակված', nf(res.played)),
    tile(L ? 'Не вышло' : 'Չհեռարձակված', nf(res.missed)),
    res.by_addr?.length ? tile(L ? 'Часов отключения' : 'Անջատված ժամեր', nf(res.off_hours || 0)) : null,
    tile(L ? 'Выполнение' : 'Կատարում', pct)));
  if (res.restored) card.append(h('div', { class: 'small', style: 'color:var(--warn);margin-top:10px', text: '↩️ ' + (L
    ? 'Это сохранённый расчёт из открытого АКТа. Чтобы пересчитать по свежему мониторингу — выберите источник выше.'
    : 'Սա բացված ԱԿՏ-ի պահված հաշվարկն է: Թարմ մոնիտորինգով վերահաշվելու համար ընտրեք աղբյուրը վերևում:') }));

  const warns = [], infos = [];
  if (res.empty_days?.length) warns.push(`⚠️ ${res.empty_days.length} ${L ? 'дней без данных' : 'օր՝ առանց տվյալների'} (${res.empty_days[0]}…)`);
  if (res.future?.length) warns.push(`⏳ ${res.future.length} ${L ? 'дн. ещё не наступили (мониторинга нет) — посчитаны как вышедшие'
    : 'օր դեռ չի եկել (մոնիտորինգ չկա)՝ հաշվվել են որպես հեռարձակված'}: ${res.future[0]} – ${res.future[res.future.length - 1]}`);
  if (res.nodata?.length) warns.push(`⚠️ ${res.nodata.length} ${L ? 'дн. нет листа в мониторинге — посчитаны как вышедшие' : 'օրվա թերթ չկա մոնիտորինգում՝ հաշվվել են որպես հեռարձակված'}: ${res.nodata.slice(0, 4).join(', ')}${res.nodata.length > 4 ? ' …' : ''}`);
  if (res.missing_months?.length) warns.push(`⛔ ${L ? 'нет файла мониторинга за' : 'մոնիտորինգի ֆայլ չկա'}: ${res.missing_months.join(', ')}`);
  if (res.files?.length) infos.push(`📁 ${L ? 'Файлы' : 'Ֆայլեր'}: ${res.files.join(' · ')}`);
  if (res.match) infos.push(`📍 ${L ? 'Адресов в акте' : 'Հասցե ԱԿՏ-ում'}: ${res.match.total} · `
    + `${L ? 'были сбои' : 'խափանում է եղել'}: ${res.match.matched} · ${L ? 'без сбоев' : 'առանց խափանման'}: ${res.match.total - res.match.matched}`);
  if (res.statuses?.length) infos.push(`📊 ${L ? 'Не вышло по статусам' : 'Չհեռարձակված՝ ըստ կարգավիճակի'}: `
    + res.statuses.map(s => `${s.name} — ${nf(s.spots)}`).join(' · '));
  (res.warnings || []).forEach(w => warns.push('⚠️ ' + w));
  if (warns.length || infos.length) card.append(h('div', { style: 'margin:12px 0' },
    ...infos.map(w => h('div', { class: 'small muted', text: w })),
    ...warns.map(w => h('div', { class: 'small', style: 'color:var(--warn)', text: w }))));
  if (res.matches?.length) {
    const rows = res.matches.map((m, i) => [i + 1, m.addr, m.obj ? `${m.obj}` : (L ? '— сбоев не было' : '— խափանում չի եղել')]);
    card.append(h('details', { style: 'margin:6px 0 10px' },
      h('summary', { class: 'small', style: 'cursor:pointer', text: '🔎 ' + (L ? 'Сверка адресов с мониторингом' : 'Հասցեների համեմատումը մոնիտորինգի հետ') }),
      h('div', { class: 'scroll', style: 'margin-top:8px' }, table(['N', L ? 'Адрес в акте' : 'Հասցե ԱԿՏ-ում',
        L ? 'Объект в мониторинге' : 'Օբյեկտ մոնիտորինգում'], rows))));
  }

  // --- 🔌 անջատումները ըստ հասցեների՝ ԺԱՄԵՐՈՎ (առաջինը, ամենակարևորը)
  if (res.by_addr?.length) {
    const off = offRows(res.by_addr, L);
    card.append(h('h3', { style: 'margin-top:14px', text: '🔌 ' + (L ? 'Когда была отключена реклама (адрес · день · часы)'
      : 'Երբ է գովազդն անջատված եղել (հասցե · օր · ժամեր)') }));
    if (off.length) card.append(h('div', { class: 'scroll' }, table(['N', L ? 'Адрес' : 'Հասցե', L ? 'Дата' : 'Ամսաթիվ',
      L ? 'Часы отключения' : 'Անջատված ժամերը', { label: L ? 'Не вышло' : 'Չհեռարձակված', num: true }], off)));
    else card.append(h('div', { class: 'small', style: 'color:var(--ok)', text: '✅ ' + (L ? 'Отключений не зафиксировано' : 'Անջատումներ չեն գրանցվել') }));
  }

  // --- ըստ ժամերի (եթե ժամեր չկան, օր.՝ ֆայլում միայն ամսաթիվ՝ ըստ օրերի)
  if (res.hours?.length) {
    const hp = res.hours.reduce((a, x) => a + x.planned, 0);
    const hm = Math.min(res.hours.reduce((a, x) => a + x.missed, 0), hp), ha = hp - hm;
    card.append(h('h3', { style: 'margin-top:14px', text: '🕒 ' + (L ? 'По часам (за весь период)' : 'Ըստ ժամերի (ամբողջ ժամանակահատվածի համար)') }),
      table([L ? 'Час' : 'Ժամ', { label: L ? 'План' : 'Նախատեսված', num: true },
        { label: L ? 'Вышло' : 'Հեռարձակված', num: true }, { label: L ? 'Не вышло' : 'Չհեռարձակված', num: true },
        { label: L ? 'Выполнение' : 'Կատարում', num: true }],
      res.hours.map(x => ({ cls: x.missed ? 'warnrow' : '', cells: [x.label, nf(x.planned), nf(x.played), nf(x.missed), x.pct === null || x.pct === undefined ? '—' : x.pct + '%'] })),
      { total: [t('word.total'), nf(hp), nf(ha), nf(hm), hp ?(Math.round(1000 * ha / hp) / 10) + '%' : '—'] }));
  } else {
    card.append(h('h3', { style: 'margin-top:14px', text: L ? 'По дням' : 'Ըստ օրերի' }),
      h('div', { class: 'tiny muted', style: 'margin-bottom:6px', text: L
        ? 'В файле нет времени выходов — расчёт по часам невозможен, показано по дням.'
        : 'Ֆայլում հեռարձակման ժամեր չկան՝ ժամերով հաշվել հնարավոր չէ, ցույց է տրված ըստ օրերի:' }),
      table([L ? 'День' : 'Օր', { label: L ? 'План' : 'Նախատեսված', num: true },
        { label: L ? 'Вышло' : 'Հեռարձակված', num: true }, { label: L ? 'Не вышло' : 'Չհեռարձակված', num: true },
        { label: L ? 'Выполнение' : 'Կատարում', num: true }],
      res.days.map(d => [d.label, nf(d.planned), nf(d.played), nf(d.missed), d.pct === null ? '—' : d.pct + '%']),
      { total: [t('word.total'), nf(res.planned), nf(res.played), nf(res.missed), pct] }));
  }

  if (res.clips?.length) card.append(h('h3', { style: 'margin-top:14px', text: t('word.clips') }),
    table([t('word.name'), { label: L ? 'Вышло' : 'Հեռարձակված', num: true }],
      res.clips.map(c => [c.name, nf(c.played)])));
  if (res.by_addr?.length) {
    card.append(h('h3', { style: 'margin-top:14px', text: t('word.addresses') }),
      h('div', { class: 'scroll' }, table(['N', L ? 'Объект' : 'Օբյեկտ', L ? 'Адрес' : 'Հասցե',
        { label: L ? 'План' : 'Նախատեսված', num: true }, { label: L ? 'Вышло' : 'Հեռարձակված', num: true },
        { label: L ? 'Не вышло' : 'Չհեռարձակված', num: true }, { label: L ? 'Часов откл.' : 'Անջ. ժամ', num: true }],
      res.by_addr.map((a, i) => [i + 1, a.obj, a.addr, nf(a.planned), nf(a.played), nf(a.missed), a.off_hours || 0]))));
  }

  const result = h('div');
  const make = h('button', { class: 'btn primary' }, '✅ ' + (L ? 'Создать АКТ' : 'Ստեղծել ԱԿՏ'));
  make.addEventListener('click', async () => {
    loader(true, L ? 'Готовлю АКТ…' : 'ԱԿՏ-ը պատրաստվում է…');
    try {
      const r = await api('/api/act/create', { method: 'POST', body: {
        client: A.client, contract: A.contract || '—', start: A.start, end: A.end,
        days: res.days, hours: res.hours || [], clips: res.clips, by_addr: res.by_addr,
        logo_net: A.logoNet === '' ? null : Number(A.logoNet), seal: A.seal } });
      clear(result).append(filesResult(r.files, r.note));
      toast(t('msg.ready'));
      S.meta.clients = await api('/api/clients', { quiet: true }).catch(() => S.meta.clients);
      result.scrollIntoView({ behavior: 'smooth' });
    } catch (e) { /* toast-ը ցույց է տրվել */ } finally { loader(false); }
  });
  card.append(h('div', { class: 'row', style: 'margin-top:16px' }, make,
    h('span', { class: 'tiny muted', text: L ? 'Word + PDF (если есть конвертер) и копия в хранилище'
      : 'Word + PDF (եթե փոխարկիչ կա) և պատճենը պահոցում' })));
  return h('div', {}, card, result);
}

function tile(k, v) {
  return h('div', { class: 'tile' }, h('div', { class: 'k', text: k }), h('div', { class: 'v', text: v }));
}
async function printTable(res, L) {
  const fmt = d => d.split('-').reverse().join('.');
  const r = await api('/api/print/act', { method: 'POST', body: {
    client: A.client, period: `${fmt(A.start)} — ${fmt(A.end)}`, days: res.days, hours: res.hours || [],
    by_addr: (res.by_addr || []).map(a => ({ addr: a.addr, off_hours: a.off_hours, off_detail: a.off_detail,
      missed: a.missed, off_list: a.off_list })),
    planned: res.planned, played: res.played, missed: res.missed, pct: res.pct } });
  window.open(r.url, '_blank');
}
