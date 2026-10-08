// 🏷 Պահեստ՝ ➕ Ավելացնել -> ինչ է դա -> որտեղ է գտնվում (օր.՝ mini PC) + որոնում, նկարներ, տպել
import { S, api, clear, confirmDlg, debounce, dt, emptyBox, field, h, loader, modal, nf, photoButton, setField,
  t, toast } from '../core.js';

const photoUrl = p => `/api/warehouse/photo?path=${encodeURIComponent(p)}`;

export const sub = () => S.lang === 'ru' ? 'Оборудование: что это и где находится'
  : 'Սարքերը՝ ինչ է դա և որտեղ է գտնվում';

const F = { q: '', category: '', status: '', location: '', sort: 'updated', view: 'cards' };

export async function render() {
  const L = S.lang === 'ru' ? 1 : 0;
  const root = h('div');
  const listBox = h('div');
  const statsBox = h('div', { class: 'grid c4', style: 'margin-bottom:16px' });

  const q = h('input', { type: 'search', value: F.q,
    placeholder: L ? 'Поиск: название, где находится, серийник, описание…'
      : 'Որոնել՝ անուն, որտեղ է, սերիական, նկարագրություն…' });
  const cat = h('select', {}, h('option', { value: '' }, L ? 'Все типы' : 'Բոլոր տեսակները'),
    ...S.meta.warehouse.categories.map(c => h('option', { value: c, selected: c === F.category }, c)));
  const st = h('select', {}, h('option', { value: '' }, L ? 'Любое состояние' : 'Ցանկացած վիճակ'),
    ...S.meta.warehouse.statuses.map(c => h('option', { value: c, selected: c === F.status }, c)));
  const sort = h('select', {},
    h('option', { value: 'updated' }, L ? 'Сначала новые' : 'Նախ նորերը'),
    h('option', { value: 'name' }, L ? 'По названию' : 'Ըստ անվան'),
    h('option', { value: 'location' }, L ? 'По месту' : 'Ըստ տեղի'),
    h('option', { value: 'qty' }, L ? 'По количеству' : 'Ըստ քանակի'));
  sort.value = F.sort;
  const addBtn = h('button', { class: 'btn primary' }, '➕ ' + t('btn.add'));
  addBtn.addEventListener('click', () => itemDlg(null, L, load));
  const viewBtn = h('button', { class: 'btn icon', title: L ? 'Вид' : 'Տեսք' }, F.view === 'cards' ? '📋' : '🔲');
  viewBtn.addEventListener('click', () => { F.view = F.view === 'cards' ? 'table' : 'cards';
    viewBtn.textContent = F.view === 'cards' ? '📋' : '🔲'; load(); });

  root.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' }, h('h2', { style: 'margin:0', text: '🏷 ' + (L ? 'Склад' : 'Պահեստ') }),
      h('div', { class: 'right' }, viewBtn,
        h('button', { class: 'btn', onClick: () => window.open(printUrl(), '_blank') }, '🖨 ' + t('btn.print')),
        h('a', { class: 'btn', href: '/api/warehouse/export' }, '📗 ' + t('btn.export')), addBtn)),
    h('div', { class: 'grid c4' }, h('div', { class: 'search', style: 'grid-column:1/-1' }, q), cat, st, sort)));
  root.append(statsBox, listBox);

  const printUrl = () => `/print/warehouse?q=${encodeURIComponent(F.q)}&category=${encodeURIComponent(F.category)}`
    + `&status=${encodeURIComponent(F.status)}&location=${encodeURIComponent(F.location)}`;

  async function load() {
    F.q = q.value; F.category = cat.value; F.status = st.value; F.sort = sort.value;
    const url = `/api/warehouse?q=${encodeURIComponent(F.q)}&category=${encodeURIComponent(F.category)}`
      + `&status=${encodeURIComponent(F.status)}&location=${encodeURIComponent(F.location)}&sort=${F.sort}`;
    const data = await api(url);
    clear(statsBox).append(
      tile(L ? 'Позиций' : 'Միավոր անուն', nf(data.stats.total), F.q || F.category || F.status ? (L ? 'по фильтру ниже' : 'ըստ զտիչի') : ''),
      tile(L ? 'Всего единиц' : 'Ընդհանուր քանակ', nf(data.stats.units), ''),
      tile(L ? 'Установлено' : 'Տեղադրված', nf(data.stats.by_status?.['տեղադրված'] || 0), ''),
      tile(L ? 'Мест хранения' : 'Պահման վայր', nf((data.stats.locations || []).length), ''));
    clear(listBox);
    if (!data.items.length) {
      listBox.append(h('div', { class: 'card' }, emptyBox(L ? 'Ничего не найдено. Нажмите «Добавить»'
        : 'Ոչինչ չգտնվեց: Սեղմեք «Ավելացնել»', '🏷')));
      return;
    }
    listBox.append(F.view === 'cards' ? cards(data.items, L, load) : tableView(data.items, L, load));
    if (data.stats.locations?.length) {
      const chips = h('div', { class: 'row tight', style: 'margin-top:12px' },
        h('span', { class: 'tiny muted', text: (L ? 'Места: ' : 'Տեղեր՝ ') }));
      data.stats.locations.slice(0, 14).forEach(loc => chips.append(h('button', {
        class: 'qchip', onClick: () => { F.location = F.location === loc ? '' : loc; load(); },
      }, loc)));
      if (F.location) chips.append(h('button', { class: 'btn sm ghost', onClick: () => { F.location = ''; load(); } },
        '✕ ' + F.location));
      listBox.append(chips);
    }
  }
  q.addEventListener('input', debounce(load, 250));
  [cat, st, sort].forEach(el => el.addEventListener('change', load));
  await load();
  return root;
}

function tile(k, v, n) {
  return h('div', { class: 'tile' }, h('div', { class: 'k', text: k }), h('div', { class: 'v', text: v }),
    h('div', { class: 'n', text: n || '' }));
}

function cards(items, L, reload) {
  const grid = h('div', { class: 'grid c3' });
  items.forEach(it => {
    const photo = it.photos?.[0];
    grid.append(h('div', { class: 'card', style: 'margin:0' },
      photo ? h('img', { class: 'thumb', src: photoUrl(photo), loading: 'lazy', decoding: 'async' }) : null,
      h('div', { class: 'card-head', style: 'margin:8px 0 6px' },
        h('h3', { style: 'margin:0', text: it.name }),
        h('div', { class: 'right' }, h('span', { class: 'badge plain', text: `${nf(it.qty)} ${it.unit}` }))),
      h('div', { class: 'small' }, '📍 ', it.location || (L ? 'место не указано' : 'տեղը նշված չէ')),
      it.description ? h('div', { class: 'small muted', style: 'margin-top:4px', text: it.description }) : null,
      h('div', { class: 'row tight', style: 'margin-top:8px' },
        h('span', { class: 'badge', text: it.category }),
        h('span', { class: 'badge ' + (it.status === 'տեղադրված' ? 'ok' : it.status === 'վերանորոգման' ? 'warn' : ''), text: it.status }),
        it.serial ? h('span', { class: 'tiny muted', text: '#' + it.serial }) : null),
      h('div', { class: 'row tight', style: 'margin-top:10px' },
        h('button', { class: 'btn sm', onClick: () => itemDlg(it, L, reload) }, '✏️'),
        h('button', { class: 'btn sm', onClick: () => photoDlg(it, L, reload) }, '📷' + (it.photos?.length ? ` ${it.photos.length}` : '')),
        h('button', { class: 'btn sm ghost', onClick: () => infoDlg(it, L) }, 'ℹ️'),
        h('div', { class: 'spacer' }),
        h('button', { class: 'btn sm danger', onClick: () => del(it, L, reload) }, '🗑'))));
  });
  return grid;
}

function tableView(items, L, reload) {
  const rows = items.map(it => h('tr', {},
    h('td', {}, h('b', { text: it.name }), it.serial ? h('div', { class: 'tiny muted', text: '#' + it.serial }) : null),
    h('td', {}, it.category),
    h('td', {}, it.location || '—'),
    h('td', { class: 'num' }, `${nf(it.qty)} ${it.unit}`),
    h('td', {}, h('span', { class: 'badge ' + (it.status === 'տեղադրված' ? 'ok' : ''), text: it.status })),
    h('td', { class: 'small muted' }, it.description || ''),
    h('td', {}, h('div', { class: 'row tight' },
      h('button', { class: 'btn sm', onClick: () => itemDlg(it, L, reload) }, '✏️'),
      h('button', { class: 'btn sm danger', onClick: () => del(it, L, reload) }, '🗑')))));
  return h('div', { class: 'card pad0' }, h('div', { class: 'tablewrap' },
    h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ...[t('word.name'), t('word.category'), t('word.location'),
        L ? 'Кол-во' : 'Քանակ', t('word.status'), t('word.description'), ''].map((x, i) =>
        h('th', { class: i === 3 ? 'num' : '' }, x)))),
      h('tbody', {}, ...rows))));
}

async function del(it, L, reload) {
  if (!await confirmDlg(L ? `Удалить «${it.name}»?` : `Ջնջե՞լ «${it.name}»-ը:`)) return;
  await api(`/api/warehouse/${it.id}`, { method: 'DELETE' });
  toast(t('msg.deleted')); reload();
}

function itemDlg(item, L, reload) {
  const it = item || {};
  const name = h('input', { type: 'text', value: it.name || '',
    placeholder: L ? 'Например: Mini PC Lenovo M900' : 'Օրինակ՝ Mini PC Lenovo M900' });
  const cat = h('select', {}, ...S.meta.warehouse.categories.map(c =>
    h('option', { value: c, selected: c === (it.category || 'Mini PC') }, c)));
  const loc = h('textarea', { rows: '2',
    placeholder: L ? 'Например: Yerevan City, Комитаса 42, серверный шкаф, 2-я полка'
      : 'Օրինակ՝ Երևան Սիթի, Կոմիտաս 42, սերվերային պահարան, 2-րդ դարակ' });
  loc.value = it.location || '';
  const desc = h('textarea', { rows: '3',
    placeholder: L ? 'Что это, зачем, характеристики, кто обслуживает…'
      : 'Ինչ է դա, ինչի համար է, բնութագրերը, ով է սպասարկում…' });
  desc.value = it.description || '';
  const qty = h('input', { type: 'number', min: '0', value: it.qty ?? 1 });
  const unit = h('select', {}, ...S.meta.warehouse.units.map(u => h('option', { value: u, selected: u === (it.unit || 'հատ') }, u)));
  const status = h('select', {}, ...S.meta.warehouse.statuses.map(s2 =>
    h('option', { value: s2, selected: s2 === (it.status || 'պահեստում') }, s2)));
  const serial = h('input', { type: 'text', value: it.serial || '', placeholder: 'SN / IMEI / MAC' });
  const resp = h('input', { type: 'text', value: it.responsible || '', placeholder: L ? 'Ответственный' : 'Պատասխանատու' });
  const tags = h('input', { type: 'text', value: (it.tags || []).join(', '), placeholder: 'bubuka, 2024, аренда' });

  // 📷 սարքի/պիտակի/փաստաթղթի նկար -> դաշտեր (նկարը կցվում է միավորին պահելիս)
  let photoFile = null;
  const photoNote = h('div', { class: 'tiny muted' });
  const photo = photoButton({
    section: 'Warehouse item (equipment: mini PC, player, speaker, router, cable…)', cls: 'btn primary block',
    note: 'Photo of the device, its label / sticker, box or invoice. Read model, serial number, etc.',
    fields: [
      { key: 'name', label: 'What the item is (type + brand + model), e.g. "Mini PC Lenovo M900"' },
      { key: 'category', type: 'enum', options: S.meta.warehouse.categories, label: 'Category' },
      { key: 'serial', label: 'Serial number / IMEI / MAC from the label' },
      { key: 'qty', type: 'number', label: 'Quantity (if shown)' },
      { key: 'unit', type: 'enum', options: S.meta.warehouse.units, label: 'Unit' },
      { key: 'location', label: 'Where it is located (if written on the photo/document)' },
      { key: 'description', type: 'text', label: 'Short description: characteristics visible on the label (CPU, RAM, power, ports…)' },
    ],
    onResult: (res, file) => {
      const v = res.values || {};
      setField(name, v.name); setField(cat, v.category); setField(serial, v.serial); setField(qty, v.qty);
      setField(unit, v.unit); setField(loc, v.location);
      if (v.description && !desc.value.trim()) setField(desc, v.description);
      if (/^image\//.test(file.type)) {
        photoFile = file;
        photoNote.textContent = '📎 ' + (L ? 'Фото будет прикреплено к позиции: ' : 'Նկարը կկցվի միավորին՝ ') + file.name;
      }
    } });

  const body = h('div', {},
    h('div', { style: 'margin-bottom:12px' }, photo, photoNote),
    field('1. ' + (L ? 'Что это?' : 'Ինչ է դա՞') + ' *', name,
      { hint: L ? 'Название устройства или предмета' : 'Սարքի կամ իրի անվանումը' }),
    h('div', { class: 'grid c2' }, field(t('word.category'), cat), field(t('word.status'), status)),
    field('2. ' + t('word.location'), loc,
      { hint: L ? 'Адрес, объект, шкаф, полка — как найти' : 'Հասցե, օբյեկտ, պահարան, դարակ՝ ինչպես գտնել' }),
    field('3. ' + t('word.description'), desc),
    h('div', { class: 'grid c3' }, field(t('word.qty'), qty), field(L ? 'Единица' : 'Միավոր', unit),
      field(L ? 'Серийный номер' : 'Սերիական համար', serial)),
    h('div', { class: 'grid c2' }, field(L ? 'Ответственный' : 'Պատասխանատու', resp),
      field(L ? 'Метки (через запятую)' : 'Պիտակներ (ստորակետով)', tags)));

  modal({
    title: item ? `✏️ ${item.name}` : '➕ ' + (L ? 'Новая позиция' : 'Նոր միավոր'),
    body,
    actions: [{ label: t('btn.cancel') }, { label: t('btn.save'), primary: true, onClick: async () => {
      if (name.value.trim().length < 2) {
        name.classList.add('bad');
        toast(L ? 'Напишите, что это' : 'Գրեք՝ ինչ է դա', 'err');
        return false;
      }
      const payload = { name: name.value, category: cat.value, location: loc.value, description: desc.value,
        qty: Number(qty.value) || 0, unit: unit.value, status: status.value, serial: serial.value,
        responsible: resp.value, tags: tags.value.split(',').map(x => x.trim()).filter(Boolean) };
      loader(true);
      try {
        const saved = item ? await api(`/api/warehouse/${item.id}`, { method: 'PUT', body: payload })
          : await api('/api/warehouse', { method: 'POST', body: payload });
        if (photoFile && saved?.id) {
          const fd = new FormData(); fd.append('file', photoFile);
          await api(`/api/warehouse/${saved.id}/photo`, { method: 'POST', form: fd }).catch(() => {});
        }
        toast(t('msg.saved')); reload();
      } catch (e) { return false; } finally { loader(false); }
    } }],
  });
}

function photoDlg(it, L, reload) {
  const inp = h('input', { type: 'file', accept: 'image/*', style: 'display:none' });
  const grid = h('div', { class: 'vgrid' });
  const draw = () => {
    clear(grid);
    (it.photos || []).forEach(p => grid.append(h('a', { href: photoUrl(p), target: '_blank' },
      h('img', { class: 'thumb', src: photoUrl(p), loading: 'lazy' }))));
    if (!(it.photos || []).length) grid.append(emptyBox(L ? 'Фото нет' : 'Նկարներ չկան', '📷'));
  };
  const zone = h('div', { class: 'dropzone' }, h('div', { class: 'dzi' }, '📷'),
    h('div', { text: L ? 'Добавить фото' : 'Ավելացնել նկար' }));
  zone.addEventListener('click', () => inp.click());
  inp.addEventListener('change', async () => {
    if (!inp.files.length) return;
    const fd = new FormData(); fd.append('file', inp.files[0]);
    loader(true);
    try {
      const updated = await api(`/api/warehouse/${it.id}/photo`, { method: 'POST', form: fd });
      it.photos = updated.photos; draw(); reload();
    } finally { loader(false); inp.value = ''; }
  });
  draw();
  modal({ title: `📷 ${it.name}`, body: h('div', {}, zone, inp, h('div', { class: 'hr' }), grid) });
}

function infoDlg(it, L) {
  const rows = [[t('word.name'), it.name], [t('word.category'), it.category], [t('word.location'), it.location || '—'],
    [t('word.qty'), `${it.qty} ${it.unit}`], [t('word.status'), it.status], ['SN', it.serial || '—'],
    [L ? 'Ответственный' : 'Պատասխանատու', it.responsible || '—'],
    [L ? 'Метки' : 'Պիտակներ', (it.tags || []).join(', ') || '—'],
    [L ? 'Добавлено' : 'Ավելացվել է', dt(it.created)], [L ? 'Изменено' : 'Փոփոխվել է', dt(it.updated)]];
  modal({ title: `ℹ️ ${it.name}`, body: h('div', {},
    h('div', { class: 'list' }, ...rows.map(([k, v]) => h('div', { class: 'li' },
      h('div', { class: 't' }, h('b', { text: k })), h('div', { style: 'text-align:right', text: String(v) })))),
    it.description ? h('p', { class: 'small', style: 'margin-top:10px', text: it.description }) : null,
    (it.history || []).length ? h('div', {}, h('h3', { style: 'margin-top:12px', text: L ? 'История' : 'Պատմություն' }),
      ...it.history.slice(-10).reverse().map(x => h('div', { class: 'tiny muted',
        text: `${dt(x.at)} — ${x.what}${x.by && x.by !== 'web' ? ` · ${x.by}` : ''}` }))) : null) });
}
