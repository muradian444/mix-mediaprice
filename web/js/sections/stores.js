// 🏪 Խանութներ՝ բոլոր ցանցերը, հասցեները և քանի գովազդային տեղ է ազատ յուրաքանչյուր հասցեում
import { S, api, clear, confirmDlg, copyText, debounce, emptyBox, field, h, isoToday, loader, modal, nf, photoButton, promptDlg,
  setField, t, toast } from '../core.js';
import { priceSite } from './pricelist.js';

/* 📷 պայմանագրի/պատվերի նկարից՝ գովազդատու, ժամկետ, նշում */
function bookingPhoto(cl, start, end, note) {
  return photoButton({ section: 'Advertiser booking in shops', cls: 'btn sm',
    note: 'Contract, order or e-mail of an advertiser.',
    fields: [{ key: 'client', label: 'Advertiser company name' },
      { key: 'start', type: 'date', label: 'Advertising start date' },
      { key: 'end', type: 'date', label: 'Advertising end date' },
      { key: 'note', label: 'Short note: contract number, clip length, etc.' }],
    onResult: res => { const v = res.values || {}; setField(cl.input, v.client); setField(start, v.start); setField(end, v.end); setField(note, v.note); } });
}

export const sub = () => S.lang === 'ru' ? 'Магазины, адреса и свободные места для рекламы'
  : 'Խանութներ, հասցեներ և ազատ գովազդային տեղեր';

const DISTRICT_RU = {
  'Կենտրոն': 'Центр', 'Արաբկիր': 'Арабкир', 'Աջափնյակ': 'Аджапняк', 'Ավան': 'Аван', 'Դավթաշեն': 'Давташен',
  'Էրեբունի': 'Эребуни', 'Մալաթիա-Սեբաստիա': 'Малатия-Себастия', 'Նոր Նորք': 'Нор-Норк', 'Նորք-Մարաշ': 'Норк-Мараш',
  'Նուբարաշեն': 'Нубарашен', 'Շենգավիթ': 'Шенгавит', 'Քանաքեռ-Զեյթուն': 'Канакер-Зейтун',
  'Երևան': 'Ереван (другие)', 'Մարզեր': 'Регионы',
};
const dname = d => S.lang === 'ru' ? (DISTRICT_RU[d] || d) : (d === 'Երևան' ? 'Երևան (այլ)' : d);
const norm = s => String(s || '').toLowerCase().replace(/[․.,:;«»"'()\-–—/]+/g, ' ').replace(/\s+/g, ' ').trim();
let logoBust = Date.now();
let districts = [];   // թաղամասերի ցանկը՝ սերվերից (հասցեի պատուհանի ընտրության համար)

export async function render(params) {
  const L = S.lang === 'ru' ? 1 : 0;
  if (params.view === 'playing') return withTabs('playing', await playingView(L, params), L);
  const ov = await api('/api/stores');
  districts = ov.districts;
  if (params.view === 'prices') return withTabs('prices', await pricesView(ov, L), L);
  const ni = params.net === undefined ? -1 : Number(params.net);
  if (ov.networks[ni]) return detail(ov, ni, L);
  return withTabs('stores', overview(ov, L), L);
}

/* ---------------------------------------------------------------- ներդիրներ */
const money = v => (v === null || v === undefined || v === '') ? '—' : `${nf(v)} ֏`;
function withTabs(cur, node, L) {
  const tab = (id, label, hash) => h('button', { class: cur === id ? 'on' : '', onClick: () => { location.hash = hash; } }, label);
  return h('div', {},
    h('div', { class: 'seg', style: 'margin-bottom:14px;flex-wrap:wrap' },
      tab('stores', '🏪 ' + (L ? 'Магазины' : 'Խանութներ'), '#/stores'),
      tab('prices', '💰 ' + (L ? 'Цены' : 'Գներ'), '#/stores?view=prices'),
      tab('playing', '🎵 ' + (L ? 'Что играет' : 'Ինչ է հնչում'), '#/stores?view=playing')),
    node);
}

/* ---------------------------------------------------------------- 💰 գներ՝ գնացուցակ (փաթեթներ, հաշվիչ) + յուրաքանչյուր խանութ */
/* 🔗 հանրային էջ (/price)՝ հաճախորդին ուղարկելու համար (առանց մուտքի) */
function shareCard(L) {
  const KIND = { domain: L ? '🌐 Домен' : '🌐 Դոմեն', internet: L ? '🌍 Интернет' : '🌍 Ինտերնետ',
    office: L ? '🏢 Офис (только в сети)' : '🏢 Գրասենյակ (միայն ցանցում)', current: L ? '📍 Текущий адрес' : '📍 Ընթացիկ հասցե' };
  const ru = u => `${u}?lang=ru`;
  let main = `${location.origin}/price`;
  const rows = h('div', { style: 'position:relative;z-index:1;display:grid;gap:8px;margin-top:18px' });
  const warn = h('p', { class: 'small', hidden: true, style: 'position:relative;z-index:1;margin:12px 0 0;opacity:.85' });
  const card = h('div', { class: 'hero', style: 'margin-bottom:16px' },
    h('div', { class: 'orb a' }), h('div', { class: 'orb b' }),
    h('div', { class: 'eyebrow', text: L ? 'ССЫЛКА ДЛЯ КЛИЕНТА' : 'ՀՂՈՒՄ ՀԱՃԱԽՈՐԴԻ ՀԱՄԱՐ' }),
    h('h2', {}, L ? 'Страница цен — ' : 'Գների էջ՝ ', h('em', { text: L ? 'отдельной ссылкой' : 'առանձին հղումով' })),
    h('p', { text: L
      ? 'Пакеты, цены и калькулятор с анимацией — без входа в систему. Цены всегда актуальные: берутся из этого раздела.'
      : 'Փաթեթներ, գներ և հաշվիչ՝ անիմացիաներով, առանց համակարգ մտնելու: Գները միշտ թարմ են՝ վերցվում են այս բաժնից:' }),
    h('div', { class: 'cta' },
      h('button', { class: 'btn primary', onClick: () => window.open(main, '_blank', 'noopener') }, '✨ ' + (L ? 'Открыть страницу' : 'Բացել էջը')),
      h('button', { class: 'btn', onClick: () => copyText(main) }, '📋 ' + (L ? 'Ссылка (арм.)' : 'Հղում (հայ.)')),
      h('button', { class: 'btn', onClick: () => copyText(ru(main)) }, '📋 ' + (L ? 'Ссылка (рус.)' : 'Հղում (ռուս.)'))),
    rows, warn);
  api('/api/stores/share', { quiet: true }).then(d => {
    const links = d.links || [];
    if (links[0]) main = links[0].url;
    rows.append(...links.map(x => h('div', { class: 'row tight', style: 'flex-wrap:wrap;gap:8px' },
      h('span', { class: 'badge', style: 'background:rgba(255,255,255,.14);color:#fff', text: KIND[x.kind] || x.kind }),
      h('code', { style: 'color:#fff;font-size:12.5px;word-break:break-all', text: x.url }),
      h('button', { class: 'btn sm', onClick: () => copyText(x.url) }, '📋 ՀԱՅ'),
      h('button', { class: 'btn sm', onClick: () => copyText(ru(x.url)) }, '📋 РУС'))));
    if (!links.some(x => x.kind === 'domain' || x.kind === 'internet')) {
      warn.hidden = false;
      warn.textContent = L
        ? '⚠️ Сейчас ссылка откроется только в офисной сети. Для клиента вне офиса запустите share_internet.bat и откройте приложение по ссылке trycloudflare.com — здесь появится интернет-ссылка. После «🌐 Обновить сайт» страница есть и на GitHub Pages: …/price.html'
        : '⚠️ Հիմա հղումը կբացվի միայն գրասենյակի ցանցում: Գրասենյակից դուրս հաճախորդի համար գործարկեք share_internet.bat-ը և բացեք հավելվածը trycloudflare.com հղումով՝ այստեղ կհայտնվի ինտերնետային հղումը: «🌐 Թարմացնել կայքը»-ից հետո էջը կա նաև GitHub Pages-ում՝ …/price.html';
    }
  }).catch(() => { /* հիմնական հղումը (ընթացիկ հասցե) արդեն աշխատում է */ });
  return card;
}

async function pricesView(ov, L) {
  const root = h('div');
  root.append(shareCard(L));
  try {
    root.append(priceSite(await api('/api/stores/pricelist'), L));
  } catch (e) { /* toast-ը ցույց է տրվել՝ ներքևի աղյուսակը աշխատում է */ }
  const inputs = [];
  const totalIncome = ov.networks.reduce((s, n) => s + (n.income || 0), 0);
  root.append(h('div', { class: 'grid c3', style: 'margin-bottom:16px' },
    tile(L ? 'С ценой' : 'Գնով', `${ov.networks.filter(n => n.price !== null).length}/${ov.networks.length}`, L ? 'сетей' : 'ցանց'),
    tile(L ? 'Доход в месяц (сейчас)' : 'Ամսական եկամուտ (հիմա)', money(totalIncome), L ? 'активные рекламодатели × цена' : 'ակտիվ գովազդատուներ × գին'),
    tile(L ? 'Особые цены адресов' : 'Հասցեների առանձին գներ',
      nf(ov.networks.reduce((s, n) => s + n.addresses.filter(a => a.price_custom).length, 0)), L ? 'адресов' : 'հասցե')));

  const tbody = h('tbody');
  ov.networks.forEach(n => {
    const inp = h('input', { type: 'text', inputmode: 'numeric', value: n.price ?? '', placeholder: '—', style: 'width:130px' });
    const note = h('input', { type: 'text', value: n.price_note || '', placeholder: L ? 'например: 30 сек, 24 выхода' : 'օր.՝ 30 վրկ, 24 անգամ' });
    inputs.push({ n, inp, note });
    const custom = n.addresses.filter(a => a.price_custom).length;
    tbody.append(h('tr', {},
      h('td', {}, h('div', { class: 'row tight' }, logoEl(n, 28), h('a', { href: `#/stores?net=${n.index}`, text: n.short }))),
      h('td', { class: 'num', text: String(n.count) }),
      h('td', {}, h('div', { class: 'inline' }, inp, h('span', { class: 'small muted', text: '֏' }))),
      h('td', {}, note),
      h('td', { class: 'small muted', text: custom ? `${custom} ${L ? 'адр. со своей ценой' : 'հասցե՝ իր գնով'}` : '' }),
      h('td', { class: 'num', text: money(n.income) })));
  });
  const save = h('button', { class: 'btn primary' }, '💾 ' + t('btn.save'));
  save.addEventListener('click', async () => {
    const rows = inputs.map(({ n, inp, note }) => ({ index: n.index, price: inp.value.trim(), note: note.value }));
    try {
      loader(true);
      const r = await api('/api/stores/prices', { method: 'POST', body: { rows } });
      toast(`${t('msg.saved')} · ${L ? 'изменено цен' : 'փոխված գներ'}: ${r.changed}`, 'ok');
      window.MM.reload();
    } catch (e) { /* toast */ } finally { loader(false); }
  });
  const logBtn = h('button', { class: 'btn' }, '🕘 ' + (L ? 'История цен' : 'Գների պատմություն'));
  logBtn.addEventListener('click', () => priceLog(L));
  root.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' },
      h('h2', { style: 'margin:0', text: '💰 ' + (L ? 'Цена каждого магазина' : 'Յուրաքանչյուր խանութի գինը') }),
      h('div', { class: 'right' }, logBtn,
        h('button', { class: 'btn', onClick: () => window.open('/print/prices', '_blank') }, '🖨 ' + t('btn.print')), save)),
    h('p', { class: 'small muted', text: L
      ? 'Цена за одно рекламное место на одном адресе в месяц (драм). Свою цену для отдельного адреса можно задать в карточке адреса. Все изменения записываются в историю.'
      : 'Գինը՝ մեկ գովազդային տեղ, մեկ հասցե, ամսական (դրամ): Առանձին հասցեի գինը՝ հասցեի քարտում: Բոլոր փոփոխությունները գրվում են պատմության մեջ:' }),
    h('div', { class: 'tablewrap' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ...[L ? 'Сеть' : 'Ցանց', L ? 'Адр.' : 'Հասց.', L ? 'Цена / мес' : 'Գին / ամիս',
        L ? 'Примечание' : 'Նշում', '', L ? 'Доход сейчас' : 'Եկամուտ հիմա'].map(x => h('th', { text: x })))),
      tbody))));
  return root;
}

async function priceLog(L) {
  let d;
  try { d = await api('/api/stores/prices/log'); } catch (e) { return; }
  modal({ title: '🕘 ' + (L ? 'История цен' : 'Գների պատմություն'), wide: true, body: d.rows.length
    ? h('div', { class: 'tablewrap' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ...[L ? 'Когда' : 'Երբ', L ? 'Кто' : 'Ով', L ? 'Сеть' : 'Ցանց', L ? 'Адрес' : 'Հասցե',
        L ? 'Было' : 'Էր', L ? 'Стало' : 'Դարձավ'].map(x => h('th', { text: x })))),
      h('tbody', {}, ...d.rows.map(r => h('tr', {}, h('td', { text: String(r.at).replace('T', ' ') }), h('td', { text: r.by }),
        h('td', { text: r.network }), h('td', { class: 'small', text: r.address || (L ? 'вся сеть' : 'ամբողջ ցանցը') }),
        h('td', { text: money(r.old) }), h('td', {}, h('b', { text: money(r.new) })))))))
    : emptyBox(L ? 'Изменений пока нет' : 'Փոփոխություններ դեռ չկան', '🕘') });
}

/* ---------------------------------------------------------------- 🎵 ինչ է հնչում՝ որ խանութում, որ հասցեում, որ հոլովակը */
async function playingView(L, params) {
  const d = await api('/api/stores/playing');
  const root = h('div');
  const q = h('input', { type: 'search', placeholder: L ? 'Поиск: магазин, адрес, рекламодатель, ролик…' : 'Որոնում՝ խանութ, հասցե, գովազդատու, հոլովակ…', value: params.q || '' });
  const clientSel = h('select', {}, h('option', { value: '' }, L ? 'Все рекламодатели' : 'Բոլոր գովազդատուները'),
    ...d.clients.map(c => h('option', { value: c }, c)));
  const nets = [...new Map(d.rows.map(r => [r.net, r.short])).entries()];
  const netSel = h('select', {}, h('option', { value: '' }, L ? 'Все сети' : 'Բոլոր ցանցերը'),
    ...nets.map(([i, s]) => h('option', { value: String(i) }, s)));
  const box = h('div');
  const addrCount = new Set(d.rows.map(r => `${r.net}|${r.addr}`)).size;
  root.append(h('div', { class: 'grid c4', style: 'margin-bottom:16px' },
    tile(L ? 'Сейчас в эфире' : 'Հիմա եթերում', nf(d.rows.length), L ? 'размещений' : 'տեղադրում'),
    tile(L ? 'Адресов' : 'Հասցեներ', nf(addrCount), L ? 'где идёт реклама' : 'որտեղ գովազդ կա'),
    tile(L ? 'Рекламодателей' : 'Գովազդատուներ', nf(d.clients.length), ''),
    tile(L ? 'Без ролика' : 'Առանց հոլովակի', nf(d.no_clip), L ? 'укажите название ролика' : 'նշեք հոլովակի անունը')));

  const setAll = h('button', { class: 'btn', disabled: true }, '🎵 ' + (L ? 'Ролик для всех адресов' : 'Հոլովակ բոլոր հասցեների համար'));
  setAll.addEventListener('click', () => clipAllDialog(clientSel.value, L));
  const printBtn = h('button', { class: 'btn' }, '🖨 ' + t('btn.print'));
  printBtn.addEventListener('click', () => window.open(`/print/playing?nets=${netSel.value}&client=${encodeURIComponent(clientSel.value)}`, '_blank'));
  root.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' },
      h('h2', { style: 'margin:0', text: '🎵 ' + (L ? `Что играет сегодня · ${d.day.split('-').reverse().join('.')}` : `Ինչ է հնչում այսօր · ${d.day.split('-').reverse().join('.')}`) }),
      h('div', { class: 'right' }, setAll, printBtn)),
    h('div', { class: 'row' }, h('div', { class: 'search', style: 'flex:1;min-width:220px' }, q), netSel, clientSel),
    box));

  function draw() {
    clear(box);
    setAll.disabled = !clientSel.value;
    const needle = norm(q.value);
    const rows = d.rows.filter(r => (!clientSel.value || r.client === clientSel.value) && (!netSel.value || String(r.net) === netSel.value)
      && (!needle || norm(`${r.short} ${r.address} ${r.client} ${r.clip} ${r.note}`).includes(needle)));
    if (!rows.length) { box.append(emptyBox(d.rows.length ? (L ? 'Ничего не найдено' : 'Ոչինչ չգտնվեց') : (L ? 'Сейчас реклама нигде не идёт' : 'Հիմա գովազդ ոչ մի տեղ չկա'), '🎵')); return; }
    const groups = new Map();
    rows.forEach(r => { const k = r.net; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(r); });
    groups.forEach(list => {
      const tb = h('tbody');
      list.forEach(r => tb.append(h('tr', {},
        h('td', {}, h('div', { text: r.address }), h('div', { class: 'tiny muted', text: dname(r.district) })),
        h('td', {}, h('b', { text: r.client })),
        h('td', {}, r.clip
          ? (r.clip_url ? h('a', { href: r.clip_url, target: '_blank', rel: 'noopener', text: '▶ ' + r.clip }) : h('span', { text: '🎵 ' + r.clip }))
          : h('span', { class: 'badge warn', text: L ? 'не указан' : 'նշված չէ' })),
        h('td', { class: 'small muted', text: `${r.start ? r.start.split('-').reverse().join('.') : '…'} — ${r.end ? r.end.split('-').reverse().join('.') : (L ? 'бессрочно' : 'անժամկետ')}` }),
        h('td', {}, h('button', { class: 'btn sm ghost', title: L ? 'Изменить ролик' : 'Փոխել հոլովակը',
          onClick: () => editBooking({ index: r.net }, { i: r.addr, address: r.address }, r, L, () => window.MM.reload()) }, '✏️')))));
      box.append(h('h3', { style: 'margin:16px 0 6px', text: `🏪 ${list[0].short} · ${list.length}` }),
        h('div', { class: 'tablewrap' }, h('table', { class: 'table' },
          h('thead', {}, h('tr', {}, ...[L ? 'Адрес' : 'Հասցե', L ? 'Рекламодатель' : 'Գովազդատու', L ? 'Ролик' : 'Հոլովակ',
            L ? 'Срок' : 'Ժամկետ', ''].map(x => h('th', { text: x })))), tb)));
    });
  }
  q.addEventListener('input', debounce(draw, 200));
  clientSel.addEventListener('change', draw);
  netSel.addEventListener('change', draw);
  draw();
  return root;
}

function clipFields(L, b = {}) {
  const clip = h('input', { type: 'text', value: b.clip || '', placeholder: L ? 'Название ролика, напр.: «Осень −20%» 30 сек' : 'Հոլովակի անունը, օր.՝ «Աշուն −20%» 30 վրկ' });
  const url = h('input', { type: 'url', value: b.clip_url || '', placeholder: 'https://drive.google.com/… (MP3)' });
  return { clip, url };
}

function clipAllDialog(client, L) {
  const f = clipFields(L);
  modal({ title: `🎵 ${client}`, body: h('div', {},
    h('p', { class: 'small muted', text: L ? 'Новый ролик будет записан во все активные размещения этого рекламодателя (во всех магазинах и адресах).'
      : 'Նոր հոլովակը կգրվի այս գովազդատուի բոլոր ակտիվ տեղադրումներում (բոլոր խանութներում և հասցեներում):' }),
    field(L ? 'Ролик' : 'Հոլովակ', f.clip), field(L ? 'Ссылка на MP3 (не обязательно)' : 'MP3 հղում (պարտադիր չէ)', f.url)),
  actions: [{ label: t('btn.cancel') }, { label: '✅ ' + t('btn.save'), primary: true, onClick: async () => {
    try {
      const r = await api('/api/stores/clip', { method: 'POST', body: { client, clip: f.clip.value, clip_url: f.url.value } });
      toast(`${t('msg.saved')}: ${r.changed}`, 'ok');
      window.MM.reload();
    } catch (e) { return false; }
  } }] });
}

function editBooking(net, a, b, L, onChange) {
  const f = clipFields(L, b);
  const start = h('input', { type: 'date', value: b.start || '' });
  const end = h('input', { type: 'date', value: b.end || '' });
  const note = h('input', { type: 'text', value: b.note || '' });
  modal({ title: `✏️ ${b.client}`, body: h('div', {},
    h('p', { class: 'small muted', text: a.address }),
    field(L ? 'Ролик (что играет)' : 'Հոլովակ (ինչ է հնչում)', f.clip),
    field(L ? 'Ссылка на MP3 (не обязательно)' : 'MP3 հղում (պարտադիր չէ)', f.url),
    h('div', { class: 'grid c2' }, field(L ? 'С' : 'Սկիզբ', start), field(L ? 'По' : 'Մինչև', end)),
    field(L ? 'Примечание' : 'Նշում', note)),
  actions: [{ label: t('btn.cancel') }, { label: '✅ ' + t('btn.save'), primary: true, onClick: async () => {
    try {
      const fresh = await api(`/api/stores/${net.index}/addresses/${a.i}/bookings/${encodeURIComponent(b.id)}`, { method: 'PUT',
        body: { clip: f.clip.value, clip_url: f.url.value, start: start.value, end: end.value, note: note.value } });
      toast(t('msg.saved'));
      onChange(fresh);
    } catch (e) { return false; }
  } }] });
}

/* ---------------------------------------------------------------- մանր բաղադրիչներ */
const PALETTE = ['#6A3DE8', '#2E8CF0', '#E8475F', '#0E9F9A', '#D97706', '#16A34A', '#DB2777', '#7C3AED', '#0284C7', '#EA580C'];
function initials(name) {
  const w = String(name).replace(/[«»"']/g, '').split(/[\s-]+/).filter(Boolean);
  return ((w[0] || '?')[0] + (w[1] ? w[1][0] : (w[0] || '').slice(1, 2))).toUpperCase();
}
function colorOf(name) {
  let x = 0;
  for (const c of String(name)) x = (x * 31 + c.charCodeAt(0)) >>> 0;
  return PALETTE[x % PALETTE.length];
}
function logoEl(net, size = 56) {
  const box = h('div', { class: 'slogo', style: `width:${size}px;height:${size}px;flex:0 0 ${size}px` });
  const fallback = () => {
    clear(box);
    box.classList.add('ini');
    box.style.background = colorOf(net.name);
    box.style.fontSize = Math.round(size * 0.36) + 'px';
    box.textContent = initials(net.short || net.name);
  };
  if (net.logo) {
    const img = h('img', { src: `${net.logo}?v=${logoBust}`, alt: net.short || net.name });
    img.addEventListener('error', fallback);
    box.append(img);
  } else fallback();
  return box;
}
function slotBar(occ, cap) {
  const r = cap ? Math.min(1, occ / cap) : 0;
  // գրադիենտը ձգվում է ամբողջ գծի երկայնքով՝ որքան շատ է զբաղված, այնքան «կարմիր» է վերջը
  return h('div', { class: 'slotbar' },
    h('i', { style: `width:${(r * 100).toFixed(1)}%;background-size:${r ? (100 / r).toFixed(1) : 100}% 100%` }));
}
function freeBadge(free, cap, L) {
  const cls = free === 0 ? 'err' : (free <= cap * 0.25 ? 'warn' : 'ok');
  const txt = free === 0 ? (L ? 'мест нет' : 'տեղ չկա') : `${nf(free)} ${L ? 'свободно' : 'ազատ'}`;
  return h('span', { class: `badge ${cls}`, text: txt });
}
function tile(k, v, n) {
  return h('div', { class: 'tile' }, h('div', { class: 'k', text: k }), h('div', { class: 'v', text: v }),
    h('div', { class: 'n', text: n }));
}
function addrCard(n, a, L, { selectable = false, checked = false, onToggle, onOpen, showNet = false } = {}) {
  const card = h('div', { class: `slotcard${a.free === 0 ? ' full' : ''}${checked ? ' sel' : ''}`, tabindex: '0' });
  if (selectable) {
    const cb = h('input', { type: 'checkbox', checked, disabled: a.free === 0 && !checked,
      title: a.free === 0 ? (L ? 'Мест нет' : 'Տեղ չկա') : '' });
    cb.addEventListener('click', e => e.stopPropagation());
    cb.addEventListener('change', () => { card.classList.toggle('sel', cb.checked); onToggle(cb.checked); });
    card.append(cb);
  }
  card.append(h('div', { class: 'sl-body' },
    h('div', { class: 'sl-addr', text: a.address }),
    showNet ? h('div', { class: 'tiny muted', text: n.short }) : null,
    slotBar(a.occupied, a.capacity),
    h('div', { class: 'sl-meta' },
      h('b', { text: `${a.occupied}/${a.capacity} · ${a.free} ${L ? 'свободно' : 'ազատ'}` }),
      h('span', { class: 'tiny muted', text: dname(a.district) })),
    a.clips?.length ? h('div', { class: 'tiny', style: 'margin-top:4px;color:var(--blue)', title: a.clips.join('\n'),
      text: `🎵 ${a.clips.slice(0, 2).join(', ')}${a.clips.length > 2 ? ' +' + (a.clips.length - 2) : ''}` }) : null,
    a.price_custom ? h('div', { class: 'tiny muted', text: `💰 ${money(a.price)}` }) : null));
  if (onOpen) {
    card.addEventListener('click', onOpen);
    card.addEventListener('keydown', e => { if (e.key === 'Enter') onOpen(); });
  }
  return card;
}

/* ---------------------------------------------------------------- բոլոր ցանցերը */
function overview(ov, L) {
  const root = h('div');
  const nets = ov.networks;
  const tot = nets.reduce((s, n) => ({ addr: s.addr + n.count, slots: s.slots + n.slots, occ: s.occ + n.occupied,
    free: s.free + n.free }), { addr: 0, slots: 0, occ: 0, free: 0 });
  root.append(h('div', { class: 'grid c4', style: 'margin-bottom:16px' },
    tile(L ? 'Сети магазинов' : 'Խանութների ցանցեր', nf(nets.length), L ? 'в списке' : 'ցանկում'),
    tile(L ? 'Адреса' : 'Հասցեներ', nf(tot.addr), L ? 'точек вещания' : 'հեռարձակման կետ'),
    tile(L ? 'Занято мест' : 'Զբաղված տեղեր', nf(tot.occ), `${L ? 'из' : 'ընդհանուր'} ${nf(tot.slots)}`),
    tile(L ? 'Свободно мест' : 'Ազատ տեղեր', nf(tot.free),
      `${ov.capacity} ${L ? 'мест на адрес' : 'տեղ մեկ հասցեում'}`)));

  const q = h('input', { type: 'search', placeholder: L ? 'Поиск: сеть или адрес…' : 'Որոնում՝ ցանց կամ հասցե…' });
  let onlyFree = false;
  const segAll = h('button', { class: 'on' }, L ? 'Все' : 'Բոլորը');
  const segFree = h('button', {}, L ? 'Есть места' : 'Կա ազատ տեղ');
  const setSeg = v => { onlyFree = v; segAll.classList.toggle('on', !v); segFree.classList.toggle('on', v); draw(); };
  segAll.addEventListener('click', () => setSeg(false));
  segFree.addEventListener('click', () => setSeg(true));

  const capBtn = h('button', { class: 'btn' }, `⚙️ ${ov.capacity} ${L ? 'мест/адрес' : 'տեղ/հասցե'}`);
  capBtn.addEventListener('click', async () => {
    const v = await promptDlg(L ? 'Сколько рекламодателей помещается на одном адресе (по умолчанию для всех сетей)'
      : 'Քանի գովազդատու է տեղավորվում մեկ հասցեում (բոլոր ցանցերի համար)',
    { value: String(ov.capacity), title: L ? 'Мест на адрес' : 'Տեղեր մեկ հասցեում' });
    if (!v) return;
    await api('/api/stores/capacity', { method: 'POST', body: { capacity: Number(v) } });
    toast(t('msg.saved'));
    window.MM.reload();
  });
  const pubBtn = h('button', { class: 'btn primary' }, '🌐 ' + (L ? 'Обновить сайт' : 'Թարմացնել կայքը'));
  pubBtn.addEventListener('click', () => publish(L));

  root.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' },
      h('h2', { text: '🏪 ' + (L ? 'Магазины и рекламные места' : 'Խանութներ և գովազդային տեղեր') }),
      h('div', { class: 'right' },
        h('button', { class: 'btn', onClick: () => window.open('/print/stores', '_blank') }, '🖨 ' + t('btn.print')),
        capBtn, pubBtn)),
    h('div', { class: 'row' }, h('div', { class: 'search', style: 'flex:1;min-width:220px' }, q),
      h('div', { class: 'seg' }, segAll, segFree))));

  const grid = h('div', { class: 'storegrid' });
  const found = h('div');
  root.append(grid, found);

  function draw() {
    clear(grid); clear(found);
    const needle = norm(q.value);
    const hits = [];
    nets.forEach(n => {
      const nameHit = !needle || norm(n.name).includes(needle);
      const addrHits = needle ? n.addresses.filter(a => norm(a.address).includes(needle)) : [];
      if (!nameHit && !addrHits.length) return;
      if (onlyFree && !n.free) return;
      grid.append(netCard(n, L));
      addrHits.forEach(a => { if (!onlyFree || a.free) hits.push([n, a]); });
    });
    if (!grid.children.length) grid.append(emptyBox(L ? 'Ничего не найдено' : 'Ոչինչ չգտնվեց', '🔍'));
    if (hits.length) {
      found.append(h('div', { class: 'card', style: 'margin-top:16px' },
        h('h3', { text: `📍 ${L ? 'Найденные адреса' : 'Գտնված հասցեներ'} · ${hits.length}` }),
        h('div', { class: 'slotgrid' }, ...hits.slice(0, 80).map(([n, a]) => addrCard(n, a, L, {
          showNet: true, onOpen: () => openAddress(n, a, L, () => window.MM.reload()) })))));
    }
  }
  q.addEventListener('input', debounce(draw, 200));
  draw();
  return root;
}

function netCard(n, L) {
  return h('button', { class: 'storecard', onClick: () => { location.hash = `#/stores?net=${n.index}`; } },
    logoEl(n, 54),
    h('div', { class: 'sc-body' },
      h('div', { class: 'sc-name', text: n.short }),
      h('div', { class: 'tiny muted', text: `${n.count} ${L ? 'адр.' : 'հասցե'} · ${n.capacity} ${L ? 'мест/адрес' : 'տեղ/հասցե'}` }),
      h('div', { class: 'tiny', style: 'color:var(--violet);font-weight:700', text: n.price !== null ? `💰 ${money(n.price)} / ${L ? 'мес' : 'ամիս'}` : '' }),
      slotBar(n.occupied, n.slots),
      h('div', { class: 'sc-foot' },
        h('span', { class: 'tiny muted', text: `${nf(n.occupied)}/${nf(n.slots)}` }),
        freeBadge(n.free, n.slots, L))));
}

/* ---------------------------------------------------------------- մեկ ցանց */
function detail(ov, ni, L) {
  let net = ov.networks[ni];
  const sel = new Set();
  let district = '';
  const root = h('div');
  const head = h('div', { class: 'card' });
  const chips = h('div', { class: 'chips' });
  const grid = h('div', { class: 'slotgrid' });
  const q = h('input', { type: 'search', placeholder: L ? 'Поиск адреса…' : 'Որոնել հասցե…' });
  q.addEventListener('input', debounce(() => drawGrid(), 200));

  const selCount = h('b', { text: '0' });
  const bookBtn = h('button', { class: 'btn primary', disabled: true },
    '➕ ' + (L ? 'Добавить рекламодателя' : 'Ավելացնել գովազդատու'));
  bookBtn.addEventListener('click', () => bookDialog(net, [...sel], L, res => { sel.clear(); update(res); }));
  const clearBtn = h('button', { class: 'btn ghost', onClick: () => { sel.clear(); drawGrid(); } }, t('btn.none'));
  const selbar = h('div', { class: 'selbar' },
    h('span', {}, (L ? 'Выбрано: ' : 'Ընտրված է՝ '), selCount, L ? ' адр.' : ' հասցե'),
    h('div', { class: 'spacer' }), clearBtn, bookBtn);

  const update = fresh => { ov = fresh; net = ov.networks[ni]; drawHead(); drawChips(); drawGrid(); };
  const refresh = async () => update(await api('/api/stores'));

  function drawHead() {
    clear(head);
    const file = h('input', { type: 'file', accept: 'image/*', hidden: true });
    file.addEventListener('change', async () => {
      if (!file.files[0]) return;
      const fd = new FormData();
      fd.append('file', file.files[0]);
      loader(true);
      try {
        await api(`/api/stores/${ni}/logo`, { method: 'POST', form: fd });
        logoBust = Date.now();
        toast(t('msg.saved'));
        await refresh();
      } catch (e) { /* toast */ } finally { loader(false); }
    });
    const capIn = h('input', { type: 'number', min: '1', max: '500', value: String(net.capacity), style: 'width:90px' });
    const capSave = h('button', { class: 'btn sm' }, '💾');
    capSave.addEventListener('click', async () => {
      update(await api(`/api/stores/${ni}`, { method: 'PUT', body: { capacity: Number(capIn.value) || '' } }));
      toast(t('msg.saved'));
    });
    const priceIn = h('input', { type: 'text', inputmode: 'numeric', value: net.price ?? '', placeholder: '֏', style: 'width:110px' });
    const priceSave = h('button', { class: 'btn sm' }, '💾');
    priceSave.addEventListener('click', async () => {
      update(await api(`/api/stores/${ni}/price`, { method: 'PUT', body: { price: priceIn.value.trim() } }));
      toast(t('msg.saved'));
    });
    head.append(
      h('div', { class: 'storehead' },
        h('button', { class: 'btn sm ghost', onClick: () => { location.hash = '#/stores'; } }, '← ' + t('btn.back')),
        logoEl(net, 72),
        h('div', { style: 'flex:1;min-width:200px' },
          h('h2', { style: 'margin:0', text: net.short }),
          h('div', { class: 'small muted', text: net.name }),
          h('div', { class: 'small', style: 'margin-top:4px;color:var(--blue);font-weight:600',
            text: `${L ? 'Всего' : 'Ընդամենը'} — ${net.count} ${L ? 'адресов' : 'հասցե'}` })),
        h('div', { class: 'row tight' },
          freeBadge(net.free, net.slots, L),
          net.full ? h('span', { class: 'badge err', text: `${net.full} ${L ? 'адр. заполнено' : 'հասցե լցված'}` }) : null)),
      slotBar(net.occupied, net.slots),
      h('div', { class: 'row', style: 'margin-top:12px' },
        file,
        h('button', { class: 'btn sm', onClick: () => file.click() },
          '🖼 ' + (net.logo ? (L ? 'Сменить лого' : 'Փոխել լոգոն') : (L ? 'Загрузить лого' : 'Վերբեռնել լոգո'))),
        net.logo ? h('button', { class: 'btn sm ghost danger', onClick: async () => {
          if (!await confirmDlg(L ? 'Удалить логотип?' : 'Ջնջե՞լ լոգոն:')) return;
          await api(`/api/stores/${ni}/logo`, { method: 'DELETE' });
          await refresh();
        } }, '🗑') : null,
        h('div', { class: 'spacer' }),
        h('span', { class: 'small muted', text: L ? 'Цена/мес:' : 'Գին/ամիս՝' }), priceIn, priceSave,
        h('span', { class: 'small muted', text: L ? 'Мест на адрес:' : 'Տեղ մեկ հասցեում՝' }), capIn, capSave,
        h('button', { class: 'btn sm', onClick: () => window.open(`/print/stores?nets=${ni}`, '_blank') }, '🖨 ' + t('btn.print'))));
  }

  function drawChips() {
    clear(chips);
    const counts = {};
    net.addresses.forEach(a => { counts[a.district] = (counts[a.district] || 0) + 1; });
    const order = ov.districts.filter(d => counts[d]);
    if (district && !counts[district]) district = '';
    const chip = (d, label) => h('button', { class: `chip${district === d ? ' on' : ''}`,
      onClick: () => { district = d; drawChips(); drawGrid(); } }, label);
    chips.append(chip('', `${L ? 'Все' : 'Բոլորը'} · ${net.count}`), ...order.map(d => chip(d, `${dname(d)} · ${counts[d]}`)));
  }

  function visible() {
    const needle = norm(q.value);
    return net.addresses.filter(a => (!district || a.district === district) && (!needle || norm(a.address).includes(needle)));
  }
  function drawGrid() {
    clear(grid);
    const rows = visible();
    rows.forEach(a => grid.append(addrCard(net, a, L, {
      selectable: true, checked: sel.has(a.i),
      onToggle: on => { on ? sel.add(a.i) : sel.delete(a.i); syncSel(); },
      onOpen: () => openAddress(net, a, L, update),
    })));
    if (!rows.length) grid.append(emptyBox(L ? 'Ничего не найдено' : 'Ոչինչ չգտնվեց', '🔍'));
    syncSel();
  }
  function syncSel() {
    selCount.textContent = String(sel.size);
    bookBtn.disabled = !sel.size;
    clearBtn.hidden = !sel.size;
  }
  const selectAll = h('button', { class: 'btn sm ghost', style: 'color:var(--violet);text-decoration:underline' },
    L ? 'Отметить все' : 'Նշել բոլորը');
  selectAll.addEventListener('click', () => { visible().forEach(a => { if (a.free) sel.add(a.i); }); drawGrid(); });

  drawHead(); drawChips(); drawGrid();
  root.append(head, h('div', { class: 'card' },
    h('div', { class: 'row', style: 'margin-bottom:10px' },
      h('div', { class: 'search', style: 'flex:1;min-width:200px' }, q), selectAll),
    chips, grid, selbar));
  return root;
}

/* ---------------------------------------------------------------- պատուհաններ */
function clientInput(L) {
  const id = 'mm-clients-' + Math.random().toString(36).slice(2, 7);
  const input = h('input', { type: 'text', list: id, placeholder: L ? 'Название компании' : 'Ընկերության անվանումը' });
  return { input, wrap: h('div', {}, input, h('datalist', { id }, ...(S.meta?.clients || []).map(c => h('option', { value: c })))) };
}

function bookDialog(net, indexes, L, onDone) {
  const cl = clientInput(L);
  const start = h('input', { type: 'date', value: isoToday() });
  const end = h('input', { type: 'date' });
  const note = h('input', { type: 'text', placeholder: L ? 'Например: договор 0056, ролик 20 сек' : 'Օր.՝ պայմանագիր 0056, հոլովակ 20 վրկ' });
  const cf = clipFields(L);
  modal({
    title: '➕ ' + (L ? 'Новый рекламодатель' : 'Նոր գովազդատու'),
    body: h('div', {},
      h('div', { class: 'row' }, h('p', { class: 'small muted', style: 'flex:1;margin:0', text: `${net.short} · ${indexes.length} ${L ? 'адресов' : 'հասցե'}` }),
        bookingPhoto(cl, start, end, note)),
      field(L ? 'Рекламодатель' : 'Գովազդատու', cl.wrap),
      h('div', { class: 'grid c2' },
        field(L ? 'С' : 'Սկիզբ', start),
        field(L ? 'По (пусто — бессрочно)' : 'Մինչև (դատարկ՝ անժամկետ)', end)),
      field(L ? 'Ролик (что будет играть)' : 'Հոլովակ (ինչ է հնչելու)', cf.clip),
      field(L ? 'Ссылка на MP3 (не обязательно)' : 'MP3 հղում (պարտադիր չէ)', cf.url),
      field(L ? 'Примечание' : 'Նշում', note),
      h('div', { class: 'hint', text: L ? 'Место освобождается автоматически после даты окончания.'
        : 'Ավարտի ամսաթվից հետո տեղը ինքնաբերաբար ազատվում է:' })),
    actions: [{ label: t('btn.cancel') }, { label: '✅ ' + t('btn.save'), primary: true, onClick: async () => {
      try {
        const r = await api(`/api/stores/${net.index}/bookings`, { method: 'POST',
          body: { client: cl.input.value, addresses: indexes, start: start.value, end: end.value, note: note.value,
            clip: cf.clip.value, clip_url: cf.url.value } });
        report(r, L);
        onDone(r.overview);
      } catch (e) { return false; }
    } }],
  });
}

function report(r, L) {
  if (r.added) toast(`${L ? 'Добавлено на адресах' : 'Ավելացվեց հասցեներում'}: ${r.added}`, 'ok');
  if (r.full?.length) toast(`${L ? 'Мест нет' : 'Տեղ չկա'}:\n${r.full.join('\n')}`, 'warn');
  if (r.duplicates?.length) toast(`${L ? 'Уже есть на этих адресах' : 'Արդեն կա այս հասցեներում'}:\n${r.duplicates.join('\n')}`, 'warn');
  if (!r.added && !r.full?.length && !r.duplicates?.length) toast(L ? 'Ничего не добавлено' : 'Ոչինչ չավելացվեց', 'warn');
}

function openAddress(net, a, L, onChange) {
  const today = isoToday();
  const fmt = d => d ? d.split('-').reverse().join('.') : '…';
  let m = null;
  const books = h('div', { class: 'list', style: 'margin-bottom:14px' });
  (a.bookings || []).forEach(b => {
    const active = !b.end || b.end >= today;
    books.append(h('div', { class: 'li' },
      h('div', { class: 't' }, h('b', { text: b.client }),
        h('div', { class: 's', text: `${fmt(b.start)} — ${b.end ? fmt(b.end) : (L ? 'бессрочно' : 'անժամկետ')}${b.note ? ' · ' + b.note : ''}` }),
        h('div', { class: 's', style: 'color:var(--blue)', text: b.clip ? '🎵 ' + b.clip : (L ? '🎵 ролик не указан' : '🎵 հոլովակը նշված չէ') })),
      h('span', { class: `badge ${active ? 'ok' : 'plain'}`, text: active ? (L ? 'активно' : 'ակտիվ') : (L ? 'завершено' : 'ավարտված') }),
      h('button', { class: 'btn sm ghost', title: L ? 'Изменить ролик / срок' : 'Փոխել հոլովակը / ժամկետը',
        onClick: () => { m.close(); editBooking(net, a, b, L, onChange); } }, '✏️'),
      h('button', { class: 'btn sm ghost danger', title: t('btn.delete'), onClick: async () => {
        if (!await confirmDlg(L ? `Убрать «${b.client}» с этого адреса?` : `Հեռացնե՞լ «${b.client}»-ը այս հասցեից:`)) return;
        const fresh = await api(`/api/stores/${net.index}/addresses/${a.i}/bookings/${encodeURIComponent(b.id)}`, { method: 'DELETE' });
        toast(t('msg.deleted'));
        m.close();
        onChange(fresh);
      } }, '🗑')));
  });
  if (!(a.bookings || []).length) books.append(emptyBox(L ? 'Пока никого — все места свободны' : 'Դեռ ոչ ոք չկա՝ բոլոր տեղերն ազատ են', '📭'));

  const cl = clientInput(L);
  const start = h('input', { type: 'date', value: today });
  const end = h('input', { type: 'date' });
  const note = h('input', { type: 'text' });
  const cf = clipFields(L);
  const priceIn = h('input', { type: 'text', inputmode: 'numeric', value: a.price_custom ? String(a.price) : '',
    placeholder: net.price !== null && net.price !== undefined ? `${net.price} (${L ? 'цена сети' : 'ցանցի գինը'})` : '֏' });
  const capIn = h('input', { type: 'number', min: '1', max: '500', value: a.capacity_custom ? String(a.capacity) : '',
    placeholder: String(net.capacity) });
  const distSel = h('select', {}, ...districts.map(d => h('option', { value: d, selected: d === a.district }, dname(d))));
  const saveSet = h('button', { class: 'btn sm' }, '💾 ' + t('btn.save'));
  saveSet.addEventListener('click', async () => {
    await api(`/api/stores/${net.index}/addresses/${a.i}/price`, { method: 'PUT', body: { price: priceIn.value.trim() } });
    const fresh = await api(`/api/stores/${net.index}/addresses/${a.i}`, { method: 'PUT',
      body: { capacity: capIn.value ? Number(capIn.value) : '', district: distSel.value } });
    toast(t('msg.saved'));
    m.close();
    onChange(fresh);
  });

  m = modal({
    title: '📍 ' + a.address,
    wide: true,
    body: h('div', {},
      h('div', { class: 'row', style: 'margin-bottom:8px' }, logoEl(net, 36), h('b', { text: net.short }),
        h('div', { class: 'spacer' }), freeBadge(a.free, a.capacity, L),
        h('span', { class: 'badge plain', text: `${a.occupied}/${a.capacity}` })),
      slotBar(a.occupied, a.capacity),
      h('h3', { style: 'margin-top:16px', text: L ? 'Рекламодатели на этом адресе' : 'Գովազդատուներ այս հասցեում' }),
      books,
      a.free > 0 ? h('div', { class: 'card', style: 'background:var(--card-2);margin-bottom:12px' },
        h('div', { class: 'card-head' }, h('h3', { text: '➕ ' + (L ? 'Занять место' : 'Զբաղեցնել տեղ') }),
          h('div', { class: 'right' }, bookingPhoto(cl, start, end, note))),
        h('div', { class: 'grid c2' },
          field(L ? 'Рекламодатель' : 'Գովազդատու', cl.wrap),
          field(L ? 'Примечание' : 'Նշում', note),
          field(L ? 'Ролик' : 'Հոլովակ', cf.clip),
          field(L ? 'Ссылка на MP3' : 'MP3 հղում', cf.url),
          field(L ? 'С' : 'Սկիզբ', start),
          field(L ? 'По (пусто — бессрочно)' : 'Մինչև (դատարկ՝ անժամկետ)', end)))
        : h('p', { class: 'small', style: 'color:var(--err)', text: L ? 'Свободных мест нет.' : 'Ազատ տեղ չկա:' }),
      h('details', {},
        h('summary', { class: 'small', style: 'cursor:pointer;color:var(--muted)', text: L ? 'Настройки адреса' : 'Հասցեի կարգավորումներ' }),
        h('div', { class: 'row', style: 'margin-top:10px;align-items:flex-end' },
          h('div', { style: 'flex:1;min-width:180px' }, field(L ? 'Район' : 'Թաղամաս', distSel)),
          h('div', { style: 'width:170px' }, field(L ? 'Мест на этом адресе' : 'Տեղեր այս հասցեում', capIn)),
          h('div', { style: 'width:190px' }, field(L ? 'Цена этого адреса, ֏/мес' : 'Այս հասցեի գինը, ֏/ամիս', priceIn)),
          h('div', { class: 'field' }, saveSet)))),
    actions: [{ label: t('btn.close') }, a.free > 0 ? { label: '✅ ' + (L ? 'Занять место' : 'Զբաղեցնել'), primary: true, onClick: async () => {
      try {
        const r = await api(`/api/stores/${net.index}/bookings`, { method: 'POST',
          body: { client: cl.input.value, addresses: [a.i], start: start.value, end: end.value, note: note.value,
            clip: cf.clip.value, clip_url: cf.url.value } });
        report(r, L);
        onChange(r.overview);
      } catch (e) { return false; }
    } } : null],
  });
}

async function publish(L) {
  loader(true);
  let r;
  try {
    r = await api('/api/stores/publish', { method: 'POST', body: {} });
  } catch (e) { return; } finally { loader(false); }
  modal({
    title: '🌐 ' + (L ? 'Сайт обновлён' : 'Կայքը թարմացված է'),
    body: h('div', {},
      h('p', { text: L
        ? `Папка docs/ обновлена: ${r.networks} сетей, ${r.logos} логотипов. Имена рекламодателей на сайт не попадают — только количество мест.`
        : `docs/ թղթապանակը թարմացվեց՝ ${r.networks} ցանց, ${r.logos} լոգո: Կայքում երևում են միայն տեղերի քանակները, գովազդատուների անունները՝ ոչ:` }),
      h('p', { class: 'small', text: L ? 'Чтобы изменения появились по ссылке:' : 'Որպեսզի փոփոխությունները երևան հղումով՝' }),
      h('ol', { class: 'small' },
        h('li', { text: L ? 'Откройте GitHub Desktop' : 'Բացեք GitHub Desktop-ը' }),
        h('li', { text: L ? 'Напишите короткое описание → Commit to main' : 'Գրեք կարճ նկարագրություն → Commit to main' }),
        h('li', { text: L ? 'Нажмите Push origin — через 1–2 минуты сайт обновится' : 'Սեղմեք Push origin — 1–2 րոպեից կայքը կթարմանա' }))),
  });
}
