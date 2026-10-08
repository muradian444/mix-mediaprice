// 📡 Տեխ. մոնիտորինգ՝ ներկառուցված (նախկին Google Sheets + Apps Script «MyMusicMonitoring»)
// Օր (վանդակների աղյուսակ) · Ամիս (հաշվետվություն) · Փոստ և մատյան · Կարգավորումներ և ներմուծում
import { S, api, clear, emptyBox, field, h, isoToday, loader, modal, nf, table, toast, ymd } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Статусы музыки по объектам и часам · отчёты · почта'
  : 'Երաժշտության կարգավիճակներ՝ ըստ օբյեկտների և ժամերի · հաշվետվություններ · փոստ';

const ST = [   // [նշան, գույն, RU, HY]
  ['⚠', '#f4cccc', 'Проблема', 'Խնդիր'],
  ['📞', '#f4cccc', 'Звонок (не отвечает)', 'Զանգ (չի պատասխանում)'],
  ['🟡', '#fff2cc', 'Подтверждено менеджером', 'Հաստատված է մենեջերի կողմից'],
  ['🔧', '#cfe2f3', 'Настройка / ремонт', 'Կարգավորում / վերանորոգում'],
  ['🚧', '#fce5cd', 'Тех. причина у объекта', 'Տեխ. պատճառ օբյեկտում'],
  ['✅', '#d9ead3', 'Работает', 'Աշխատում է'],
];
const EMOJIS = ['👍', '👎', '😀', '😡', '😢', '🙏', '❓', '❗', '📞', '🔧', '⏳', '✔️', '❌', '💡', '🔥', '⭐'];
const COLOR = Object.fromEntries(ST.map(s => [s[0], s[1]]));
const sname = (sym, L) => { const s = ST.find(x => x[0] === sym); return s ? (L ? s[2] : s[3]) : sym; };
const hh = x => String(Number(x) % 24).padStart(2, '0') + ':00';
const dmy = iso => iso ? iso.split('-').reverse().join('.') : '';
const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00'); d.setDate(d.getDate() + n); return ymd(d); };

const MONTHS = [
  ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'],
  ['Հունվար', 'Փետրվար', 'Մարտ', 'Ապրիլ', 'Մայիս', 'Հունիս', 'Հուլիս', 'Օգոստոս', 'Սեպտեմբեր', 'Հոկտեմբեր', 'Նոյեմբեր', 'Դեկտեմբեր']];
const mlabel = (ym, L) => { const [y, m] = String(ym).split('-'); return `${MONTHS[L ? 0 : 1][Number(m) - 1] || ym} ${y}`; };

const T = { tab: 'day', day: '', month: '', filter: '', onlyMarked: true, status: null, timer: null, logLevel: '' };

export async function render(params = {}) {
  const L = S.lang === 'ru';
  if (['day', 'month', 'mail', 'settings'].includes(params.tab)) T.tab = params.tab;   // #/techmon?tab=month&month=2026-09
  if (/^\d{4}-\d{2}-\d{2}$/.test(params.day || '')) T.day = params.day;
  if (/^\d{4}-\d{2}$/.test(params.month || '')) T.month = params.month;
  if (!T.day) T.day = isoToday();
  T.status = await api('/api/techmon/status');
  if (!T.month) T.month = (T.status.months[0] || {}).month || isoToday().slice(0, 7);
  const root = h('div');
  const head = h('div'), body = h('div');
  root.append(head, body);

  const TABS = [['day', '📋', L ? 'День' : 'Օր'], ['month', '📊', L ? 'Месяц' : 'Ամիս'],
    ['mail', '📬', L ? 'Почта и журнал' : 'Փոստ և մատյան'], ['settings', '⚙️', L ? 'Настройки и импорт' : 'Կարգավորումներ և ներմուծում']];
  const drawHead = () => {
    clear(head);
    const st = T.status;
    const t = st.today_totals || {};
    head.append(h('div', { class: 'grid c4', style: 'margin-bottom:14px' },
      tile(L ? 'Сегодня ⚠' : 'Այսօր ⚠', nf(t['⚠'] || 0), L ? `объектов: ${st.today_objects}` : `օբյեկտ՝ ${st.today_objects}`),
      tile(L ? 'Записей в базе' : 'Գրառում բազայում', nf(st.cells), L ? `объектов: ${nf(st.objects)}` : `օբյեկտ՝ ${nf(st.objects)}`),
      tile(L ? 'Почта' : 'Փոստ', !st.configured ? (L ? 'не настроена' : 'չի կարգավորված')
        : (st.enabled ? (st.running ? '⏳' : '✅') : '⏸'), st.last_run ? (L ? 'проверка: ' : 'ստուգում՝ ') + st.last_run : ''),
      tile(L ? 'Не распознано' : 'Չճանաչված', nf(st.unrec), st.recent_errors ? `❌ ${st.recent_errors}` : '')));
    head.append(h('div', { class: 'seg', style: 'margin-bottom:14px;flex-wrap:wrap' }, ...TABS.map(([id, ic, title]) =>
      h('button', { class: T.tab === id ? 'on' : '', onClick: () => { T.tab = id; drawHead(); drawBody(); } }, `${ic} ${title}`))));
  };
  const drawBody = () => {
    clearInterval(T.timer);
    clear(body);
    const fn = { day: dayTab, month: monthTab, mail: mailTab, settings: settingsTab }[T.tab];
    Promise.resolve(fn(body, L, root, async () => { T.status = await api('/api/techmon/status'); drawHead(); }))
      .catch(e => { if (e.status !== 401) body.append(emptyBox(String(e.message || e), '⚠️')); });
  };
  drawHead();
  drawBody();
  return root;
}

function tile(k, v, n) {
  const long = String(v).length > 7;
  return h('div', { class: 'tile' }, h('div', { class: 'k', text: k }),
    h('div', { class: 'v', style: long ? 'font-size:18px;line-height:1.5' : '', text: v }), h('div', { class: 'n', text: n || '' }));
}

/* ====================================================================== 📋 ՕՐ */
function dayTab(box, L, root, refreshHead) {
  const bar = h('div', { class: 'card' });
  const grid = h('div', { class: 'card pad0', style: 'margin-top:14px' });
  box.append(bar, grid);
  let data = null;

  const dayInp = h('input', { type: 'date', value: T.day, style: 'width:auto;flex:0 0 auto' });
  const go = d => { T.day = d; dayInp.value = d; load(); };
  dayInp.addEventListener('change', () => { if (dayInp.value) go(dayInp.value); });
  const search = h('input', { type: 'text', placeholder: L ? 'Поиск объекта / адреса…' : 'Որոնել օբյեկտ / հասցե…', value: T.filter });
  search.addEventListener('input', () => { T.filter = search.value; drawGrid(); });
  const marked = h('input', { type: 'checkbox', checked: T.onlyMarked });
  marked.addEventListener('change', () => { T.onlyMarked = marked.checked; load(); });
  const legend = h('div', { class: 'row tight', style: 'margin-top:10px' });

  bar.append(
    h('div', { class: 'card-head' }, h('h2', { text: '📋 ' + (L ? 'Статусы по дню' : 'Կարգավիճակներ ըստ օրվա') }),
      h('div', { class: 'right' },
        h('button', { class: 'btn sm', onClick: () => addRow() }, '＋ ' + (L ? 'Добавить отметку' : 'Ավելացնել նշում')),
        h('button', { class: 'btn sm', title: L ? 'Обновить' : 'Թարմացնել', onClick: () => load() }, '🔄'))),
    h('div', { class: 'row' },
      h('button', { class: 'btn icon', onClick: () => go(addDays(T.day, -1)) }, '◀'), dayInp,
      h('button', { class: 'btn icon', onClick: () => go(addDays(T.day, 1)) }, '▶'),
      h('button', { class: 'btn sm', onClick: () => go(isoToday()) }, L ? 'Сегодня' : 'Այսօր'),
      h('div', { style: 'flex:1;min-width:200px' }, search),
      h('label', { class: 'check' }, marked, L ? 'Только с отметками' : 'Միայն նշումներով')),
    legend);

  async function load() {
    try { data = await api(`/api/techmon/day?day=${T.day}&show_all=${T.onlyMarked ? 0 : 1}`, { quiet: true }); }
    catch (e) { clear(grid).append(emptyBox(e.message, '⚠️')); return; }
    drawLegend();
    drawGrid();
    refreshHead();
  }
  function drawLegend() {
    clear(legend);
    ST.forEach(([sym, bg, ru, hy]) => legend.append(h('span', { class: 'badge', style: `background:${bg};color:#222`,
      title: L ? ru : hy }, `${sym} ${data.totals[sym] || 0}`)));
    if (!data.covered) legend.append(h('span', { class: 'badge warn', text: L ? 'за этот день данных нет' : 'այս օրվա տվյալներ չկան' }));
  }
  function drawGrid() {
    clear(grid);
    if (!data) return;
    const q = T.filter.trim().toLowerCase();
    const rows = data.rows.filter(r => !q || (r.obj + ' ' + r.addr).toLowerCase().includes(q));
    if (!rows.length) {
      grid.append(emptyBox(data.rows.length ? (L ? 'Ничего не найдено' : 'Ոչինչ չգտնվեց')
        : (data.covered ? (L ? '🎉 В этот день проблем не было' : '🎉 Այդ օրը խնդիրներ չեն եղել')
          : (L ? 'За этот день данных нет' : 'Այս օրվա տվյալներ չկան')), '📭'));
      return;
    }
    const thead = h('tr', {}, h('th', { class: 'tm-sticky', text: L ? 'Объект / адрес' : 'Օբյեկտ / հասցե' }),
      ...data.hours.map(x => h('th', { class: 'tm-c', text: hh(x) })), h('th', { text: '' }));
    const tbody = rows.map(r => h('tr', {},
      h('td', { class: 'tm-sticky' }, h('div', { class: 'tm-obj', text: r.obj, title: r.obj }), h('div', { class: 'tm-addr', text: r.addr, title: r.addr })),
      ...data.hours.map(x => {
        const c = r.cells[String(x)];
        return h('td', { class: 'tm-c' + (c ? ' on' : '') + (c && c.auto ? ' auto' : ''),
          style: c ? `background:${COLOR[c.s] || 'transparent'}` : '',
          title: c ? c.note + (c.emoji || c.remark ? `\n---\n${c.emoji} ${c.remark}${c.remark_user ? ` (${c.remark_user})` : ''}` : '') : '',
          onClick: () => cellDialog(r, x, c) }, c ? c.s : '', c && c.emoji ? h('sup', { text: c.emoji }) : null,
        c && c.remark && !c.emoji ? h('sup', { text: '💬' }) : null);
      }),
      h('td', {}, r.problems ? h('button', { class: 'btn sm', title: L ? 'Сменить статус всех ⚠ в строке' : 'Փոխել տողի բոլոր ⚠-ը',
        onClick: () => rowDialog(r) }, '⚠→') : '')));
    grid.append(h('div', { class: 'tablewrap tm-wrap' }, h('table', { class: 'tm-grid' }, h('thead', {}, thead), h('tbody', {}, ...tbody))));
  }

  /* վանդակի պատուհան՝ կարգավիճակ + մեկնաբանություն + պատմություն */
  async function cellDialog(row, hour, cell) {
    const comment = h('textarea', { rows: '2', placeholder: L ? 'Комментарий (необязательно)' : 'Մեկնաբանություն (ոչ պարտադիր)' });
    comment.value = cell?.remark || '';
    let emoji = cell?.emoji || '';
    const emoBar = h('div', { style: 'display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px' });
    const drawEmo = () => {
      clear(emoBar);
      EMOJIS.forEach(e => emoBar.append(h('button', { type: 'button', class: 'btn sm' + (emoji === e ? ' primary' : ''),
        style: 'font-size:18px;padding:2px 8px', onClick: () => { emoji = emoji === e ? '' : e; drawEmo(); } }, e)));
    };
    drawEmo();
    const pick = h('div', { class: 'grid c2', style: 'margin-bottom:10px' });
    let m;
    const saveRemark = async (e, t) => api('/api/techmon/remark', { method: 'POST',
      body: { day: T.day, obj: row.obj, addr: row.addr, hour, emoji: e, remark: t } });
    const apply = async status => {
      try {
        await api('/api/techmon/cell', { method: 'POST', body: { day: T.day, obj: row.obj, addr: row.addr, hour, status } });
        if (status && (emoji !== (cell?.emoji || '') || comment.value.trim() !== (cell?.remark || ''))) await saveRemark(emoji, comment.value);
        m.close(); toast('✅'); load();
      } catch (e) { /* toast */ }
    };
    ST.forEach(([sym, bg, ru, hy]) => pick.append(h('button', { class: 'btn' + (cell && cell.s === sym ? ' primary' : ''),
      style: `justify-content:flex-start;gap:8px;${cell && cell.s === sym ? '' : `border-left:6px solid ${bg}`}`, onClick: () => apply(sym) },
    `${sym} ${L ? ru : hy}`)));
    const hist = h('div', { class: 'tiny muted' });
    const body = h('div', {},
      h('div', { class: 'small', style: 'margin-bottom:8px' }, h('b', { text: row.obj }), h('div', { class: 'muted', text: `${row.addr} · ${dmy(T.day)} ${hh(hour)}` })),
      pick, field(L ? 'Смайлик и комментарий' : 'Սմայլիկ և մեկնաբանություն', h('div', {}, emoBar, comment)),
      cell ? h('div', { style: 'display:flex;gap:6px;margin-bottom:8px' },
        h('button', { class: 'btn sm primary', onClick: async () => {
          try { await saveRemark(emoji, comment.value); m.close(); toast('✅'); load(); } catch (e) { /* toast */ }
        } }, '💾 ' + (L ? 'Сохранить комментарий' : 'Պահել մեկնաբանությունը')),
        (cell.emoji || cell.remark) ? h('button', { class: 'btn sm danger', onClick: async () => {
          try { await saveRemark('', ''); m.close(); toast('✅'); load(); } catch (e) { /* toast */ }
        } }, '🗑 ' + (L ? 'Снять смайлик и комментарий' : 'Հանել սմայլիկը և մեկնաբանությունը')) : null,
        cell.remark_user ? h('span', { class: 'tiny muted', text: cell.remark_user }) : null) : null,
      cell ? h('details', { style: 'margin-bottom:8px' }, h('summary', { class: 'small', text: L ? 'Заметка ячейки' : 'Վանդակի նշումը' }),
        h('pre', { class: 'small', style: 'white-space:pre-wrap;margin:6px 0', text: cell.note })) : null,
      hist);
    m = modal({ title: `${cell ? cell.s : '·'} ${hh(hour)}`, body, actions: [
      cell ? { label: '🧹 ' + (L ? 'Очистить ячейку' : 'Մաքրել վանդակը'), danger: true, onClick: async () => { await apply(''); return false; } } : null,
      { label: L ? 'Закрыть' : 'Փակել' }] });
    try {
      const rows = await api(`/api/techmon/history?day=${T.day}&obj=${encodeURIComponent(row.obj)}&addr=${encodeURIComponent(row.addr)}&hour=${hour}`, { quiet: true });
      if (rows.length) hist.append(h('b', { text: (L ? 'История' : 'Պատմություն') + ':' }), ...rows.map(r =>
        h('div', { text: `${(r.ts || '').replace('T', ' ').slice(0, 16)} · ${r.old || '∅'} → ${r.new || '∅'} · ${r.user || (r.source === 'mail' ? '✉️ auto' : r.source)}` })));
    } catch (e) { /* history is optional */ }
  }

  /* տողի բոլոր ⚠-ը մեկ քայլով (օր.՝ մենեջերը հաստատեց, որ երաժշտությունը աշխատում է) */
  function rowDialog(row) {
    const items = Object.entries(row.cells).filter(([, c]) => c.s === '⚠').map(([hr]) => ({ day: T.day, obj: row.obj, addr: row.addr, hour: Number(hr) }));
    const comment = h('textarea', { rows: '2', placeholder: L ? 'Комментарий (необязательно)' : 'Մեկնաբանություն (ոչ պարտադիր)' });
    const pick = h('div', { class: 'grid c2', style: 'margin-bottom:10px' });
    let m;
    ST.filter(s => s[0] !== '⚠').forEach(([sym, bg, ru, hy]) => pick.append(h('button', { class: 'btn', style: `justify-content:flex-start;border-left:6px solid ${bg}`,
      onClick: async () => {
        await api('/api/techmon/cells', { method: 'POST', body: { items: items.map(i => ({ ...i, status: sym })), comment: comment.value } });
        m.close(); toast(`✅ ${items.length}`); load();
      } }, `${sym} ${L ? ru : hy}`)));
    m = modal({ title: `⚠ → ? (${items.length})`, body: h('div', {}, h('div', { class: 'small', style: 'margin-bottom:8px' }, h('b', { text: row.obj }),
      h('div', { class: 'muted', text: items.map(i => hh(i.hour)).join(', ') })), pick, field(L ? 'Комментарий' : 'Մեկնաբանություն', comment)) });
  }

  /* նոր նշում՝ ցանկացած օբյեկտի/ժամի համար */
  function addRow() {
    const objs = [...new Map((data?.known || []).map(k => [k.obj, k])).values()];
    const dl = h('datalist', { id: 'tm-objs' }, ...objs.map(k => h('option', { value: k.obj })));
    const obj = h('input', { type: 'text', list: 'tm-objs', placeholder: L ? 'Объект' : 'Օբյեկտ' });
    const addr = h('input', { type: 'text', placeholder: L ? 'Адрес' : 'Հասցե' });
    obj.addEventListener('change', () => { const k = (data?.known || []).find(x => x.obj === obj.value); if (k) addr.value = k.addr; });
    const hour = h('select', {}, ...data.hours.map(x => h('option', { value: x }, hh(x))));
    const status = h('select', {}, ...ST.map(([sym, , ru, hy]) => h('option', { value: sym }, `${sym} ${L ? ru : hy}`)));
    const comment = h('input', { type: 'text', placeholder: L ? 'Комментарий' : 'Մեկնաբանություն' });
    modal({ title: '＋ ' + (L ? 'Новая отметка' : 'Նոր նշում'), body: h('div', {}, dl,
      field(L ? 'Объект' : 'Օբյեկտ', obj), field(L ? 'Адрес' : 'Հասցե', addr),
      h('div', { class: 'grid c2' }, field(L ? 'Час' : 'Ժամ', hour), field(L ? 'Статус' : 'Կարգավիճակ', status)), field(L ? 'Комментарий' : 'Մեկնաբանություն', comment)),
    actions: [{ label: L ? 'Отмена' : 'Չեղարկել' }, { label: L ? 'Сохранить' : 'Պահել', primary: true, onClick: async () => {
      if (!obj.value.trim() || !addr.value.trim()) { toast(L ? 'Укажите объект и адрес' : 'Լրացրեք օբյեկտը և հասցեն', 'err'); return false; }
      await api('/api/techmon/cell', { method: 'POST', body: { day: T.day, obj: obj.value, addr: addr.value, hour: Number(hour.value), status: status.value, comment: comment.value } });
      load();
    } }] });
  }

  load().then(() => {
    // այսօրվա օրը՝ ինքնաթարմացում (եթե պատուհան բաց չէ)
    T.timer = setInterval(() => {
      if (!root.isConnected) { clearInterval(T.timer); return; }
      if (T.day === isoToday() && !document.querySelector('#modal-root .overlay')) load();
    }, 60000);
  });
}

/* ====================================================================== 📊 ԱՄԻՍ */
function monthTab(box, L) {
  const ctl = h('div', { class: 'card' });
  const out = h('div');
  box.append(ctl, out);
  const months = T.status.months;
  const sel = h('select', { style: 'width:auto' }, ...(months.length ? months : [{ month: T.month, events: 0 }]).map(m =>
    h('option', { value: m.month, selected: m.month === T.month }, `${mlabel(m.month, L)} (${nf(m.events)})`)));
  sel.addEventListener('change', () => { T.month = sel.value; load(); });
  ctl.append(h('div', { class: 'card-head' }, h('h2', { text: '📊 ' + (L ? 'Отчёт за месяц' : 'Ամսական հաշվետվություն') }),
    h('div', { class: 'right' }, sel,
      h('a', { class: 'btn sm', href: `/api/techmon/month.xlsx?month=${T.month}`, id: 'tm-xl' }, '⬇️ Excel'),
      h('button', { class: 'btn sm', onClick: () => window.open(`/print/techmon?month=${T.month}`, '_blank') }, '🖨 ' + (L ? 'Печать' : 'Տպել')),
      S.user?.role === 'admin' ? h('button', { class: 'btn sm', onClick: async () => {
        loader(true, L ? 'Отправляю отчёт…' : 'Ուղարկում եմ հաշվետվությունը…');
        try { const r = await api('/api/techmon/report/send', { method: 'POST', body: { month: T.month } }); toast('📧 ' + r.to.join(', ')); }
        catch (e) { /* toast */ } finally { loader(false); }
      } }, '📧 ' + (L ? 'Отправить' : 'Ուղարկել')) : null)));

  async function load() {
    clear(out);
    document.getElementById('tm-xl')?.setAttribute('href', `/api/techmon/month.xlsx?month=${T.month}`);
    let r;
    try { r = await api(`/api/techmon/month?month=${T.month}`); } catch (e) { return; }
    if (!r.events) { out.append(h('div', { class: 'card' }, emptyBox(L ? 'За этот месяц записей нет' : 'Այս ամսվա գրառումներ չկան'))); return; }
    const t = r.totals;
    out.append(h('div', { class: 'grid c4', style: 'margin:14px 0' },
      tile(L ? 'Событий' : 'Իրադարձություն', nf(r.events), `${r.days_covered}/${r.days_in_month} ${L ? 'дн. с данными' : 'օր տվյալներով'}`),
      tile(L ? 'Объектов с проблемами' : 'Խնդրով օբյեկտ', nf(r.objects_affected), ''),
      tile('⚠ / 📞', `${nf(t['⚠'])} / ${nf(t['📞'])}`, L ? 'проблемы / не дозвонились' : 'խնդիր / չպատասխանեցին'),
      tile(L ? 'Пик проблем' : 'Խնդիրների պիկ', r.worst_hour !== null ? hh(r.worst_hour) : '—', L ? 'час с макс. ⚠' : 'ժամ առավել ⚠-ով')));

    // օրերի գծապատկեր + ժամերի ջերմային քարտեզ
    const maxDay = Math.max(1, ...r.by_day.map(d => d.missed));
    const bars = h('div', { class: 'tm-bars' }, ...r.by_day.map(d => h('div', { class: 'tm-bar' + (d.covered ? '' : ' off'),
      title: `${dmy(d.day)}: ⚠ ${d['⚠']} · 📞 ${d['📞']} · 🟡 ${d['🟡']} · 🔧 ${d['🔧']} · 🚧 ${d['🚧']}` },
    h('i', { style: `height:${Math.round(100 * d.missed / maxDay)}%` }), h('span', { text: d.label.slice(0, 2) }))));
    const maxH = Math.max(1, ...Object.values(r.heat).map(x => x['⚠']));
    const heat = h('div', { class: 'tm-heat' }, ...r.hours.map(x => { const v = r.heat[String(x)]['⚠'];
      return h('div', { class: 'tm-hc', style: `background:rgba(214,60,60,${(0.08 + 0.8 * v / maxH).toFixed(2)})`, title: `${hh(x)} · ⚠ ${v}` },
        h('b', { text: String(v) }), h('div', { text: hh(x).slice(0, 2) })); }));
    out.append(h('div', { class: 'grid c2' },
      h('div', { class: 'card' }, h('h3', { text: '📅 ' + (L ? 'По дням (не вышло)' : 'Ըստ օրերի (չհեռարձակված)') }), bars),
      h('div', { class: 'card' }, h('h3', { text: '⏰ ' + (L ? 'Ошибки ⚠ по часам' : '⚠ ըստ ժամերի') }), heat)));

    // համեմատություն
    const curL = mlabel(r.month, L), prevL = mlabel(r.prev_month, L);
    out.append(h('div', { class: 'card' }, h('h3', { text: `📈 ${L ? 'Сравнение с' : 'Համեմատություն՝'} ${prevL}` }),
      r.prev_has_data ? null : h('p', { class: 'small muted', text: L ? 'За прошлый месяц данных нет' : 'Նախորդ ամսվա տվյալներ չկան' }),
      table([L ? 'Показатель' : 'Ցուցանիշ', { label: curL, num: true }, { label: prevL, num: true }, { label: 'Δ', num: true }, { label: '%', num: true }],
        r.compare.map(c => [`${c.status} ${sname(c.status, L)}`, nf(c.cur), nf(c.prev),
          h('span', { style: `color:${c.delta > 0 && c.status !== '✅' ? 'var(--err)' : (c.delta < 0 ? 'var(--ok)' : 'inherit')}`, text: (c.delta > 0 ? '+' : '') + c.delta }),
          c.pct === null ? '—' : c.pct + '%']))));

    // օբյեկտների աղյուսակ
    const q = h('input', { type: 'text', placeholder: L ? 'Поиск…' : 'Որոնել…' });
    const tb = h('div');
    let showAll = false;
    const drawT = () => {
      clear(tb);
      const f = q.value.trim().toLowerCase();
      let rows = r.rows.filter(x => !f || (x.obj + ' ' + x.addr).toLowerCase().includes(f));
      const total = rows.length;
      if (!showAll) rows = rows.slice(0, 60);
      tb.append(table([L ? 'Объект' : 'Օբյեկտ', L ? 'Адрес' : 'Հասցե', ...ST.map(s => ({ label: s[0], num: true })),
        { label: L ? 'Дней' : 'Օր', num: true }, { label: L ? 'Доступн.' : 'Հասանելի', num: true }, { label: L ? 'Пик' : 'Պիկ', num: true }],
      rows.map(x => [x.obj, x.addr, ...ST.map(s => x.counts[s[0]] || ''), x.days, x.uptime === null ? '—' : x.uptime + '%',
        x.worst_hour ? hh(x.worst_hour) : ''])));
      if (total > rows.length) tb.append(h('button', { class: 'btn sm', style: 'margin-top:8px', onClick: () => { showAll = true; drawT(); } },
        `${L ? 'Показать все' : 'Ցույց տալ բոլորը'} (${total})`));
    };
    q.addEventListener('input', drawT);
    out.append(h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h3', { text: '📋 ' + (L ? 'По объектам' : 'Ըստ օբյեկտների') }),
      h('div', { class: 'right' }, q)), tb));
    drawT();

    // թոփեր
    const tops = h('div', { class: 'grid c2' });
    ST.forEach(([sym, , ru, hy]) => {
      const list = r.tops[sym];
      if (!list.length) return;
      tops.append(h('details', { class: 'card', open: sym === '⚠' }, h('summary', { class: 'small', style: 'cursor:pointer;font-weight:700',
        text: `${sym} ${L ? 'ТОП' : 'ՏՈՓ'} — ${L ? ru : hy}` }),
      h('div', { class: 'list', style: 'margin-top:8px' }, ...list.slice(0, 10).map((x, i) => h('div', { class: 'li' },
        h('span', { class: 'badge', text: String(i + 1) }), h('div', { class: 't' }, h('b', { text: x.obj }), h('div', { class: 's', text: x.addr })),
        h('span', { class: 'badge plain', text: String(x.n) }))))));
    });
    out.append(tops);
  }
  load();
}

/* ====================================================================== 📬 ՓՈՍՏ ԵՎ ՄԱՏՅԱՆ */
function mailTab(box, L, root, refreshHead) {
  const stat = h('div', { class: 'card' });
  const unrec = h('div', { class: 'card', style: 'margin-top:14px' });
  const logBox = h('div', { class: 'card', style: 'margin-top:14px' });
  box.append(stat, unrec, logBox);

  const drawStat = () => {
    clear(stat);
    const run = h('button', { class: 'btn primary', onClick: runNow }, '▶️ ' + (L ? 'Проверить почту сейчас' : 'Ստուգել փոստը հիմա'));
    if (T.status.running) {
      run.setAttribute('disabled', '');
      run.textContent = '⏳ ' + (L ? 'Идёт проверка…' : 'Ստուգվում է…') + (T.status.progress ? ` ${T.status.progress}` : '');
    }
    stat.append(h('div', { class: 'card-head' }, h('h2', { text: '📬 ' + (L ? 'Чтение писем' : 'Նամակների ընթերցում') }), h('div', { class: 'right' }, run)),
      !T.status.configured
        ? h('p', { class: 'small', style: 'color:var(--warn)', text: '⚠️ ' + (L ? 'Почта не настроена. Откройте «Настройки и импорт» → введите почту и пароль приложения.'
          : 'Փոստը կարգավորված չէ: Բացեք «Կարգավորումներ և ներմուծում» և լրացրեք փոստը և հավելվածի գաղտնաբառը:') })
        : h('div', { class: 'small' },
          h('div', { text: `${T.status.enabled ? '✅' : '⏸'} ${L ? 'Авто-проверка' : 'Ավտո-ստուգում'}: ${T.status.enabled ? (L ? `каждые ${T.status.interval_min} мин` : `ամեն ${T.status.interval_min} րոպեն մեկ`) : (L ? 'выключена' : 'անջատված է')}` }),
          h('div', { class: 'muted', text: `${L ? 'Последняя проверка' : 'Վերջին ստուգում'}: ${T.status.last_run || '—'}` }),
          T.status.last_result ? h('div', { class: 'muted', text: T.status.last_result }) : null));
  };
  let polling = false;
  async function runNow() {
    if (polling) return;
    polling = true;
    T.status.running = true; drawStat();
    api('/api/techmon/run', { method: 'POST', body: {} }).catch(() => {});
    const poll = async () => {
      try { T.status = await api('/api/techmon/status', { quiet: true }); } catch { T.status.running = false; }
      drawStat();
      if (T.status.running && root.isConnected) setTimeout(poll, 1000);
      else { polling = false; refreshHead(); loadUnrec(); loadLog(); }
    };
    setTimeout(poll, 600);
  }

  async function loadUnrec() {
    const rows = await api('/api/techmon/unrec', { quiet: true }).catch(() => []);
    clear(unrec).append(h('div', { class: 'card-head' }, h('h3', { text: `🧩 ${L ? 'Не распознанные письма' : 'Չճանաչված նամակներ'} (${rows.length})` })));
    if (!rows.length) { unrec.append(h('p', { class: 'small muted', text: L ? 'Всё распознано ✓' : 'Ամեն ինչ ճանաչված է ✓' })); return; }
    unrec.append(h('div', { class: 'list scroll sm' }, ...rows.slice(0, 80).map(r => h('div', { class: 'li' },
      h('div', { class: 't' }, h('b', { text: r.subject || '(без темы)' }), h('div', { class: 's', text: `${r.mail_date} · ${r.reason}` })),
      h('button', { class: 'btn sm', onClick: () => resolveDlg(r) }, '✍️'),
      h('button', { class: 'btn sm', title: L ? 'Скрыть' : 'Թաքցնել', onClick: async () => { await api('/api/techmon/unrec/dismiss', { method: 'POST', body: { msg_id: r.msg_id } }); loadUnrec(); refreshHead(); } }, '✕')))));
  }
  function resolveDlg(r) {
    const m = (r.subject || '').match(/\[(\d+)\]\s*([^(]+?)\s*\(\s*([^)]+?)\s*\)/);
    const dm = (r.mail_date || '').match(/(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):/);
    const obj = h('input', { type: 'text', value: m ? m[2].trim() : '' });
    const addr = h('input', { type: 'text', value: m ? m[3].trim() : '' });
    const day = h('input', { type: 'date', value: dm ? `${dm[3]}-${dm[2]}-${dm[1]}` : isoToday() });
    const hour = h('input', { type: 'number', min: '0', max: '24', value: dm ? (Number(dm[4]) || 24) : 9 });
    const status = h('select', {}, ...ST.map(([sym, , ru, hy]) => h('option', { value: sym }, `${sym} ${L ? ru : hy}`)));
    modal({ title: '✍️ ' + (L ? 'Разобрать вручную' : 'Լուծել ձեռքով'), body: h('div', {}, h('p', { class: 'small muted', text: r.reason }),
      field(L ? 'Объект' : 'Օբյեկտ', obj), field(L ? 'Адрес' : 'Հասցե', addr),
      h('div', { class: 'grid c3' }, field(L ? 'Дата' : 'Ամսաթիվ', day), field(L ? 'Час' : 'Ժամ', hour), field(L ? 'Статус' : 'Կարգավիճակ', status))),
    actions: [{ label: L ? 'Отмена' : 'Չեղարկել' }, { label: L ? 'Поставить' : 'Դնել', primary: true, onClick: async () => {
      await api('/api/techmon/unrec/resolve', { method: 'POST', body: { msg_id: r.msg_id, obj: obj.value, addr: addr.value, day: day.value, hour: Number(hour.value), status: status.value } });
      loadUnrec(); refreshHead();
    } }] });
  }

  async function loadLog() {
    const rows = await api(`/api/techmon/log?limit=200&level=${T.logLevel}`, { quiet: true }).catch(() => []);
    const lv = h('select', {}, ...[['', L ? 'Все' : 'Բոլորը'], ['INFO', 'INFO'], ['WARN', 'WARN'], ['ERROR', 'ERROR']].map(([v, n]) =>
      h('option', { value: v, selected: v === T.logLevel }, n)));
    lv.addEventListener('change', () => { T.logLevel = lv.value; loadLog(); });
    clear(logBox).append(h('div', { class: 'card-head' }, h('h3', { text: '📜 ' + (L ? 'Журнал' : 'Մատյան') }), h('div', { class: 'right' }, lv)),
      rows.length ? table(['Время', 'Lvl', L ? 'Сообщение' : 'Հաղորդագրություն'],
        rows.map(r => [r.ts, h('span', { class: 'badge ' + (r.level === 'ERROR' ? 'err' : r.level === 'WARN' ? 'warn' : 'plain'), text: r.level }), r.msg]))
        : emptyBox(L ? 'Журнал пуст' : 'Մատյանը դատարկ է'));
  }
  drawStat(); loadUnrec(); loadLog();
  if (T.status.running) runNow();
}

/* ====================================================================== ⚙️ ԿԱՐԳԱՎՈՐՈՒՄՆԵՐ ԵՎ ՆԵՐՄՈՒԾՈՒՄ */
async function settingsTab(box, L, root, refreshHead) {
  const r = await api('/api/techmon/settings');
  const s = r.settings, admin = r.is_admin;
  const inp = (key, type = 'text', ph = '') => h('input', { type, value: type === 'password' ? '' : (s[key] ?? ''), placeholder: ph, disabled: !admin });
  const f = {
    imap_user: inp('imap_user', 'text', 'monitoring@gmail.com'),
    imap_password: inp('imap_password', 'password', s.imap_password_set ? '••••••••  (' + (L ? 'сохранён' : 'պահված է') + ')' : (L ? 'пароль приложения' : 'հավելվածի գաղտնաբառ')),
    imap_host: inp('imap_host'), imap_port: inp('imap_port', 'number'), imap_folder: inp('imap_folder'),
    subject: inp('subject'), since_days: inp('since_days', 'number'), interval_min: inp('interval_min', 'number'),
    work_start: inp('work_start', 'number'), work_end: inp('work_end', 'number'), gmail_label: inp('gmail_label'),
    smtp_host: inp('smtp_host'), smtp_port: inp('smtp_port', 'number'), report_emails: inp('report_emails', 'text', 'a@x.am, b@x.am'),
  };
  const chk = (key, label) => { const c = h('input', { type: 'checkbox', checked: !!s[key], disabled: !admin }); c.dataset.key = key; return [c, h('label', { class: 'check' }, c, label)]; };
  const [cEn, lEn] = chk('enabled', L ? 'Авто-проверка почты включена' : 'Փոստի ավտո-ստուգումը միացված է');
  const [cRead, lRead] = chk('mark_read', L ? 'Помечать обработанные письма прочитанными (+ метка Gmail)' : 'Նշել մշակված նամակները կարդացված (+ Gmail պիտակ)');
  const [cRep, lRep] = chk('auto_report', L ? 'Отправлять отчёт 1-го числа в 09:00' : 'Ուղարկել հաշվետվությունը ամսվա 1-ին՝ 09:00');
  const collect = () => {
    const d = {};
    Object.entries(f).forEach(([k, el]) => { d[k] = el.type === 'number' ? Number(el.value) : el.value; });
    d.enabled = cEn.checked; d.mark_read = cRead.checked; d.auto_report = cRep.checked;
    return d;
  };
  const save = async () => { await api('/api/techmon/settings', { method: 'POST', body: collect() }); toast('✅ ' + (L ? 'Сохранено' : 'Պահված է')); };

  const mail = h('div', { class: 'card' }, h('div', { class: 'card-head' }, h('h2', { text: '📬 ' + (L ? 'Почта (откуда приходят письма мониторинга)' : 'Փոստ (որտեղից են գալիս մոնիտորինգի նամակները)') })),
    !admin ? h('p', { class: 'small', style: 'color:var(--warn)', text: L ? 'Менять настройки может только администратор.' : 'Կարգավորումները փոխել կարող է միայն ադմինը:' }) : null,
    h('div', { class: 'grid c2' }, field(L ? 'Почта (логин IMAP)' : 'Փոստ (IMAP լոգին)', f.imap_user),
      field(L ? 'Пароль приложения' : 'Հավելվածի գաղտնաբառ', f.imap_password, { hint: L ? 'Gmail: Аккаунт Google → Безопасность → Пароли приложений (нужен включённый IMAP)' : 'Gmail՝ Google հաշիվ → Անվտանգություն → Հավելվածի գաղտնաբառեր (IMAP-ը պետք է միացված լինի)' })),
    h('div', { class: 'grid c3' }, field('IMAP', f.imap_host), field(L ? 'Порт' : 'Պորտ', f.imap_port), field(L ? 'Папка' : 'Թղթապանակ', f.imap_folder)),
    h('div', { class: 'grid c3' }, field(L ? 'Тема письма содержит' : 'Թեման պարունակում է', f.subject),
      field(L ? 'Искать письма за, дней' : 'Փնտրել նամակները, օր', f.since_days), field(L ? 'Проверять каждые, мин' : 'Ստուգել ամեն, րոպե', f.interval_min)),
    h('div', { class: 'grid c3' }, field(L ? 'Часы мониторинга: с' : 'Մոնիտորինգի ժամեր՝ սկսած', f.work_start),
      field(L ? '…по (24 = 00:00)' : '…մինչև (24 = 00:00)', f.work_end), field(L ? 'Метка Gmail' : 'Gmail պիտակ', f.gmail_label)),
    h('div', { class: 'grid c3' }, field('SMTP', f.smtp_host), field(L ? 'Порт SMTP' : 'SMTP պորտ', f.smtp_port),
      field(L ? 'Получатели отчёта (через запятую; пусто = на свою почту)' : 'Հաշվետվության ստացողներ (ստորակետով; դատարկ = իր փոստին)', f.report_emails)),
    h('div', { class: 'row', style: 'margin:6px 0 12px' }, lEn, lRead, lRep),
    admin ? h('div', { class: 'row' },
      h('button', { class: 'btn primary', onClick: async () => { await save(); refreshHead(); } }, '💾 ' + (L ? 'Сохранить' : 'Պահել')),
      h('button', { class: 'btn', onClick: async () => {
        loader(true, L ? 'Проверяю подключение…' : 'Ստուգում եմ կապը…');
        try { const t = await api('/api/techmon/test', { method: 'POST', body: collect() }); toast(t.message, t.ok ? 'ok' : 'err'); }
        catch (e) { /* toast */ } finally { loader(false); }
      } }, '🔌 ' + (L ? 'Проверить подключение' : 'Ստուգել կապը'))) : null);

  // նամակի ստուգիչ
  const pSubj = h('input', { type: 'text', placeholder: L ? 'Тема письма' : 'Նամակի թեման' });
  const pText = h('textarea', { rows: '4', placeholder: L ? 'Вставьте текст письма…' : 'Տեղադրեք նամակի տեքստը…' });
  const pOut = h('div', { class: 'small', style: 'margin-top:8px' });
  const tester = h('details', { class: 'card', style: 'margin-top:14px' }, h('summary', { style: 'cursor:pointer;font-weight:700', text: '🧪 ' + (L ? 'Проверка разбора письма' : 'Նամակի վերլուծության ստուգում') }),
    h('div', { style: 'margin-top:10px' }, field('', pSubj), field('', pText),
      h('button', { class: 'btn sm', onClick: async () => {
        const p = await api('/api/techmon/parse-test', { method: 'POST', body: { subject: pSubj.value, text: pText.value } });
        clear(pOut).append(p.ok
          ? h('div', {}, `✅ ${p.obj} · ${p.addr} · id ${p.ext_id}${p.net_code ? ' · ' + p.net_code : ''}`, h('br'), `${p.event} → ${hh(p.hour)} ${p.in_hours ? '' : (L ? '(вне часов — будет проигнорировано)' : '(ժամերից դուրս է)')}${p.fallback ? (L ? ' · время из даты письма' : ' · ժամը նամակի ամսաթվից') : ''}`)
          : h('div', { style: 'color:var(--err)', text: '❌ ' + p.reason }));
      } }, L ? 'Разобрать' : 'Վերլուծել'), pOut));

  // ներմուծում
  const impBox = h('div', { class: 'card', style: 'margin-top:14px' });
  const file = h('input', { type: 'file', accept: '.xlsx,.xlsm', multiple: true, style: 'display:none' });
  const link = h('input', { type: 'text', placeholder: 'https://drive.google.com/drive/folders/…', value: S.meta.settings?.monitor_folder || '', disabled: !admin });
  const prog = h('div', { class: 'small', style: 'margin-top:8px;white-space:pre-line' });
  file.addEventListener('change', async () => {
    if (!file.files.length) return;
    const fd = new FormData();
    [...file.files].forEach(x => fd.append('files', x));
    loader(true, L ? 'Импортирую…' : 'Ներմուծում եմ…');
    try {
      const res = await api('/api/techmon/import/xlsx', { method: 'POST', form: fd });
      toast(`✅ ${res.files} ${L ? 'файлов' : 'ֆայլ'} · ${res.new} ${L ? 'новых записей' : 'նոր գրառում'}`);
      if (res.errors.length) toast(res.errors.join('\n'), 'warn');
      refreshHead();
    } catch (e) { /* toast */ } finally { loader(false); file.value = ''; }
  });
  const pollImport = async () => {
    const st = await api('/api/techmon/import/state', { quiet: true });
    prog.textContent = (st.running ? `⏳ ${st.done}/${st.total} ${st.current}\n` : '') + (st.log || []).join('\n');
    if (st.running) setTimeout(() => root.isConnected && pollImport(), 2000);
    else if (st.finished) refreshHead();
  };
  impBox.append(h('div', { class: 'card-head' }, h('h2', { text: '📥 ' + (L ? 'Импорт старых данных (один раз)' : 'Հին տվյալների ներմուծում (մեկ անգամ)') })),
    h('p', { class: 'small muted', text: L ? 'Перенесите прежние месячные файлы «… Тех мониторинг» из Google Sheets в базу приложения. После импорта Google Drive больше не нужен. Уже существующие записи не перезаписываются.'
      : 'Տեղափոխեք նախկին ամսական «… Тех мониторинг» ֆայլերը Google Sheets-ից հավելվածի բազա: Ներմուծումից հետո Google Drive-ը պետք չէ: Արդեն եղած գրառումները չեն վերագրվում:' }),
    admin ? h('div', {},
      h('div', { class: 'row' }, h('button', { class: 'btn', onClick: () => file.click() }, '📎 ' + (L ? 'Загрузить .xlsx файлы' : 'Բեռնել .xlsx ֆայլեր')), file),
      field(L ? 'Или папка Google Drive (открытая: «Все, у кого есть ссылка» — Читатель)' : 'Կամ Google Drive թղթապանակ (բաց՝ «Anyone with the link» — Viewer)', link),
      h('button', { class: 'btn primary', onClick: async () => {
        if (!link.value.trim()) { toast(L ? 'Вставьте ссылку на папку' : 'Տեղադրեք թղթապանակի հղումը', 'err'); return; }
        await api('/api/techmon/import/drive', { method: 'POST', body: { link: link.value.trim() } });
        setTimeout(pollImport, 800);
      } }, '☁️ ' + (L ? 'Импортировать из папки' : 'Ներմուծել թղթապանակից')), prog) : null);
  box.append(mail, tester, impBox);
  pollImport();
}
