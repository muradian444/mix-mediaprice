// 📄 Պայմանագրեր՝ 0046 / 0055 / 0056 շաբլոնները Word-ից (նույն դաշտերը, ինչ բոտում)
// + 📷 լրացում լուսանկարից (ռեկվիզիտներ, այցեքարտ, հին պայմանագիր) + բացում «✏️ Изменить»-ից
import { S, api, clear, field, filesResult, h, isoToday, isoToDmy, loader, modal, photoButton, setField, t,
  toast } from '../core.js';

/* Claude-ի համար՝ ինչ փնտրել յուրաքանչյուր դաշտում */
const HINTS = {
  date: ['date', 'Contract date'],
  company: ['string', 'Customer company name only — without quotes «» and without the legal form (ՍՊԸ, ԲԲԸ, ООО, LLC)'],
  director: ['string', "Customer's director: first name and last name"],
  tin: ['number', 'Customer tax ID: ՀՎՀՀ / ИНН / TIN, 8 digits'],
  bank: ['string', "Customer's bank name"],
  account: ['number', "Customer's bank account number (digits only)"],
  legal_address: ['string', "Customer's legal address"],
  email: ['string', "Customer's e-mail"],
  shop: ['string', 'Shop / supermarket / network name where audio is played'],
  points: ['string', 'Which audio items apply: 3, 4 or "3 և 4"'],
  addr_count: ['number', 'Number of shop addresses / objects'],
  addresses: ['list', 'Shop / object addresses (one per item)'],
  price: ['number', 'Monthly price in AMD (per address, or the monthly amount incl. VAT)'],
  location: ['string', 'Place where the service is provided (shopping center, address)'],
};

export const sub = () => S.lang === 'ru' ? 'Шаблоны Word заполняются автоматически'
  : 'Word շաբլոնները լրացվում են ավտոմատ';

const NOTE = {
  '0055': ['Բուբուկա վճարային պայմանագիր՝ խանութ, կետեր, հասցեներ, մեկ հասցեի գումար',
    'Платный договор Bubuka: магазин, пункты, адреса, сумма за адрес'],
  '0046': ['Սուպերմարկետ՝ անվճար և գովազդի 30%', 'Супермаркет: бесплатно и 30% рекламы'],
  '0056': ['Գովազդատուի պայմանագիր՝ վայր, ամսական գումար, 4.4 կետ', 'Договор рекламодателя: место, сумма, пункт 4.4'],
};

export async function render(params) {
  const L = S.lang === 'ru' ? 1 : 0;
  const kinds = Object.values(S.meta.flows || {});
  if (!params.kind) {
    const box = h('div');
    box.append(h('div', { class: 'card' },
      h('h2', { text: L ? 'Выберите шаблон договора' : 'Ընտրեք պայմանագրի շաբլոնը' }),
      h('div', { class: 'gradline' }),
      h('div', { class: 'grid c3' }, ...kinds.map(f => h('button', {
        class: 'pick', onClick: () => location.hash = `#/contracts?kind=${f.kind}`,
      }, h('div', { class: 'pico' }, f.kind),
        h('div', {}, h('div', { class: 'pt', text: f.title }),
          h('div', { class: 'pd', text: (NOTE[f.kind] || ['', ''])[L] })))))));
    return box;
  }
  const flow = S.meta.flows[params.kind];
  if (!flow) return h('div', { class: 'card' }, h('p', { text: 'Անհայտ շաբլոն' }));
  const pre = S.prefill?.section === 'contracts' ? S.prefill.data : null;
  S.prefill = null;
  return form(flow, L, pre);
}

function form(flow, L, prefill) {
  const data = {};
  const inputs = {};
  const box = h('div');
  const photoFields = () => flow.steps.filter(s => HINTS[s.key] && s.kind !== 'buttons_only')
    .map(s => ({ key: s.key, label: s.label, type: HINTS[s.key][0], hint: HINTS[s.key][1] }));
  box.append(h('div', { class: 'card-head' },
    h('button', { class: 'btn sm ghost', onClick: () => location.hash = '#/contracts' }, '← ' + t('btn.back')),
    h('h2', { text: `📄 ${flow.title}`, style: 'margin:0' }),
    h('span', { class: 'badge plain', text: flow.kind }),
    h('div', { class: 'right' }, photoButton({ section: `Contract ${flow.kind}: ${flow.title}`, fields: photoFields, cls: 'btn primary',
      note: 'Photo of company requisites, business card, registration certificate or an old contract with this customer.',
      onResult: res => applyValues(res.values) }))));

  const main = h('div', { class: 'card' });
  const grid = h('div', { class: 'grid c2' });
  let addrStep = null;

  flow.steps.forEach(s => {
    if (s.kind === 'addresses') { addrStep = s; return; }
    let input;
    if (s.buttons && s.buttons.length) {
      input = h('select', {}, h('option', { value: '' }, '—'),
        ...s.buttons.map(b => h('option', { value: b.value }, b.label)));
      if (s.key === 'date') {
        input = h('div', { class: 'inline' },
          h('input', { type: 'date', value: isoToday(),
            onInput: e => { data[s.key] = isoToDmy(e.target.value); } }));
        data[s.key] = isoToDmy(isoToday());
        inputs[s.key] = input.firstChild;
        grid.append(field(s.label, input, { hint: s.prompt }));
        return;
      }
    } else if (s.money || s.key === 'addr_count') {
      input = h('input', { type: 'number', min: '1', step: '1', placeholder: s.money ? '8000' : '17' });
    } else if (s.key === 'legal_address' || s.key === 'location') {
      input = h('textarea', { rows: '2', placeholder: s.prompt.slice(0, 60) });
    } else {
      input = h('input', { type: 'text' });
    }
    input.addEventListener('input', () => { data[s.key] = input.value; onCount(s.key); });
    input.addEventListener('change', () => { data[s.key] = input.value; onCount(s.key); });
    inputs[s.key] = input;
    const label = s.optional ? `${s.label} (${L ? 'необязательно' : 'ոչ պարտադիր'})` : s.label;
    grid.append(field(label, input, { hint: s.prompt }));
  });
  main.append(h('h3', { text: L ? 'Данные заказчика и договора' : 'Պատվիրատուի և պայմանագրի տվյալները' }),
    h('div', { class: 'gradline' }), grid);
  box.append(main);

  // ---------------- հասցեներ
  let addrBox = null, addrArea = null, addrInfo = null;
  if (addrStep) {
    addrArea = h('textarea', { rows: '7', placeholder: L ? 'Один адрес на строку' : 'Յուրաքանչյուր հասցեն նոր տողից' });
    addrInfo = h('span', { class: 'badge', text: '0' });
    addrArea.addEventListener('input', () => { data.addresses = lines(addrArea.value); updateInfo(); });
    const fromNets = h('button', { class: 'btn sm' }, '📍 ' + (L ? 'Взять из сетей' : 'Վերցնել ցանցերից'));
    fromNets.addEventListener('click', () => pickFromNets(addrArea, updateInfo, L));
    addrBox = h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h3', { text: '📍 ' + t('word.addresses') }),
        h('div', { class: 'right' }, addrInfo, fromNets)),
      addrArea,
      h('div', { class: 'hint', text: L ? 'Количество должно совпадать с «Количество адресов»'
        : 'Քանակը պետք է համապատասխանի «Հասցեների քանակ» դաշտին' }));
    box.append(addrBox);
  }
  function updateInfo() {
    const n = lines(addrArea.value).length;
    const need = Number(data.addr_count || 0);
    addrInfo.textContent = need ? `${n} / ${need}` : String(n);
    addrInfo.className = 'badge ' + (need && n === need ? 'ok' : (need && n > need ? 'err' : 'warn'));
  }
  function onCount(key) { if (key === 'addr_count' && addrArea) updateInfo(); }

  // ---------------- լրացուցիչ (defaults)
  if (flow.defaults.length) {
    const ex = h('div', { class: 'grid c3' });
    flow.defaults.forEach(d => {
      const inp = h('input', { type: 'number', value: d.default });
      data[d.key] = d.default;
      inp.addEventListener('input', () => { data[d.key] = inp.value; });
      inputs[d.key] = inp;
      ex.append(field(d.label, inp));
    });
    box.append(h('div', { class: 'card' },
      h('h3', { text: L ? 'Дополнительные значения (можно не менять)' : 'Լրացուցիչ արժեքներ (կարելի է չփոխել)' }),
      h('div', { class: 'gradline' }), ex));
  }

  /* 📷 լուսանկարից կամ ✏️ պահված պայմանագրից եկած արժեքները՝ դաշտերում */
  function applyValues(values) {
    if (!values) return;
    let n = 0;
    Object.entries(values).forEach(([k, v]) => {
      if (k === 'addresses') {
        if (!addrArea || !v?.length) return;
        addrArea.value = (Array.isArray(v) ? v : String(v).split(/\n/)).join('\n');
        addrArea.dispatchEvent(new Event('input'));
        addrArea.classList.add('filled');
        setTimeout(() => addrArea.classList.remove('filled'), 4000);
        n++;
        return;
      }
      if (k === 'remove44') {
        const v2 = v === true || v === 'yes' ? 'yes' : (v === false || v === 'no' ? 'no' : '');
        if (v2 && setField(inputs[k], v2)) n++;
        return;
      }
      if (setField(inputs[k], v)) n++;
    });
    if (addrArea && values.addresses?.length && !values.addr_count && inputs.addr_count && !inputs.addr_count.value) {
      setField(inputs.addr_count, values.addresses.length);
    }
    return n;
  }

  // ---------------- կոճակներ
  const result = h('div');
  const create = h('button', { class: 'btn primary' }, '✅ ' + t('btn.create'));
  const check = h('button', { class: 'btn' }, '🔍 ' + (L ? 'Проверить данные' : 'Ստուգել տվյալները'));
  check.addEventListener('click', () => submit(false));
  create.addEventListener('click', () => submit(true));
  box.append(h('div', { class: 'card' }, h('div', { class: 'row' }, check, create,
    h('span', { class: 'tiny muted', text: L ? 'Сначала проверка — потом создание' : 'Նախ ստուգում, հետո՝ ստեղծում' }))));
  box.append(result);

  async function submit(doCreate) {
    if (addrArea) data.addresses = lines(addrArea.value);
    clearErrors();
    loader(true, t('word.loading'));
    try {
      const payload = { kind: flow.kind, data };
      const res = doCreate
        ? await api('/api/contracts/create', { method: 'POST', body: payload, quiet: true })
        : await api('/api/contracts/validate', { method: 'POST', body: payload, quiet: true });
      if (res.errors && Object.keys(res.errors).length) { showErrors(res.errors, L); return; }
      if (doCreate) {
        clear(result).append(filesResult(res.files, res.note));
        toast(t('msg.ready'), 'ok');
        result.scrollIntoView({ behavior: 'smooth', block: 'start' });
        S.meta.clients = await api('/api/clients', { quiet: true }).catch(() => S.meta.clients);
      } else {
        showSummary(res.summary, L, () => submit(true));
      }
    } catch (e) {
      if (e.data && e.data.errors) showErrors(e.data.errors, L);
      else toast(e.message, 'err');
    } finally { loader(false); }
  }
  function clearErrors() {
    Object.values(inputs).forEach(i => i.classList.remove('bad'));
    box.querySelectorAll('.err').forEach(e => e.remove());
    if (addrArea) addrArea.classList.remove('bad');
  }
  function showErrors(errors, L2) {
    let first = null;
    for (const [k, msg] of Object.entries(errors)) {
      const inp = k === 'addresses' ? addrArea : inputs[k];
      if (!inp) continue;
      inp.classList.add('bad');
      const holder = inp.closest('.field') || inp.parentElement;
      holder.append(h('div', { class: 'err', text: msg }));
      if (!first) first = inp;
    }
    toast((L2 ? 'Проверьте поля: ' : 'Ստուգեք դաշտերը՝ ') + Object.keys(errors).length, 'err');
    if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  if (prefill) {
    setTimeout(() => {
      applyValues(prefill);
      toast(L ? 'Договор открыт в форме: измените поля и нажмите «Создать»'
        : 'Պայմանագիրը բացվեց ձևում՝ փոխեք դաշտերը և սեղմեք «Ստեղծել»');
    }, 0);
  }
  return box;
}

function showSummary(lines_, L, onOk) {
  const list = h('div', { class: 'list' }, ...lines_.map(x => h('div', { class: 'li' },
    h('div', { class: 't' }, h('b', { text: x.label })),
    h('div', { style: 'text-align:right;white-space:pre-line', text: x.value }))));
  modal({
    title: L ? 'Проверьте данные' : 'Ստուգեք տվյալները',
    body: h('div', {}, h('p', { class: 'small muted', text: L ? 'Если всё верно — создаём документ.'
      : 'Եթե ամեն ինչ ճիշտ է՝ ստեղծում ենք փաստաթուղթը:' }), list),
    actions: [{ label: t('btn.cancel') }, { label: '✅ ' + t('btn.create'), primary: true, onClick: onOk }],
  });
}

async function pickFromNets(area, after, L) {
  const nets = await api('/api/networks');
  const sel = new Set();
  const listBox = h('div', { class: 'list scroll' });
  const q = h('input', { type: 'search', placeholder: t('word.search') + '…' });
  const draw = () => {
    clear(listBox);
    const needle = q.value.trim().toLowerCase();
    nets.forEach(n => n.addresses.forEach((a, ai) => {
      const key = `${n.index}:${ai}`;
      if (needle && !(`${a} ${n.name}`.toLowerCase().includes(needle))) return;
      const cb = h('input', { type: 'checkbox', checked: sel.has(key) });
      cb.addEventListener('change', () => { cb.checked ? sel.add(key) : sel.delete(key); cnt.textContent = sel.size; });
      listBox.append(h('label', { class: 'li' }, cb,
        h('div', { class: 't' }, h('b', { text: a }), h('div', { class: 's', text: n.name }))));
    }));
    if (!listBox.children.length) listBox.append(h('div', { class: 'empty', text: t('word.empty') }));
  };
  const cnt = h('span', { class: 'badge', text: '0' });
  q.addEventListener('input', draw);
  draw();
  modal({
    title: '📍 ' + (L ? 'Адреса из сетей' : 'Հասցեներ ցանցերից'),
    wide: true,
    body: h('div', {}, h('div', { class: 'row', style: 'margin-bottom:10px' },
      h('div', { class: 'search', style: 'flex:1' }, q), cnt), listBox),
    actions: [{ label: t('btn.cancel') }, { label: t('btn.add'), primary: true, onClick: () => {
      const picked = [];
      nets.forEach(n => n.addresses.forEach((a, ai) => { if (sel.has(`${n.index}:${ai}`)) picked.push(a); }));
      const cur = lines(area.value);
      area.value = [...cur, ...picked.filter(p => !cur.includes(p))].join('\n');
      area.dispatchEvent(new Event('input'));
      after();
    } }],
  });
}

const lines = s => String(s || '').split(/[\r\n]+/).map(x => x.trim()).filter(Boolean);
