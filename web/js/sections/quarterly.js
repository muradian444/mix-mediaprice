// 📈 Եռամսյակային հաշվետվություն՝ սլայդներ (16:9), ձեր ֆայլերը -> PDF / PowerPoint + տպել
import { S, api, bytes, clear, confirmDlg, debounce, emptyBox, field, filesResult, h, loader,
  modal, photoButton, setField, t, toast } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Свои слайды для презентации → PDF / PPTX'
  : 'Ձեր սլայդները պրեզենտացիայի համար → PDF / PPTX';

const TYPES = ['cover', 'metrics', 'chart', 'bullets', 'text', 'photo_text', 'gallery', 'table', 'image', 'files', 'closing'];
const TYPE_IC = { cover: '🏁', text: '📝', bullets: '•', metrics: '🔢', chart: '📊', table: '🧮',
  image: '🖼', photo_text: '🖼📝', gallery: '🖼🖼', files: '📎', closing: '🙏' };

export async function render(params) {
  const L = S.lang === 'ru' ? 1 : 0;
  if (params.id) {
    const deck = await api(`/api/quarterly/${params.id}`);
    return editor(deck, L);
  }
  const decks = await api('/api/quarterly');
  const box = h('div');
  const add = h('button', { class: 'btn' }, '➕ ' + (L ? 'Пустой отчёт' : 'Դատարկ հաշվետվություն'));
  add.addEventListener('click', () => newDeck(L));
  const auto = h('button', { class: 'btn primary' }, '✨ ' + (L ? 'Отчёт из текста и фото' : 'Հաշվետվություն տեքստից և նկարներից'));
  auto.addEventListener('click', () => autoDialog(null, L));
  box.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' }, h('h2', { text: '📈 ' + (L ? 'Квартальные отчёты' : 'Եռամսյակային հաշվետվություններ') }),
      h('div', { class: 'right' }, add, auto)),
    h('p', { class: 'small', text: L
      ? '✨ Напишите своими словами, что сделано за 3 месяца, и добавьте фото — система сама разложит текст по слайдам, найдёт цифры, построит график по месяцам и подберёт фото к каждому слайду. Потом всё можно поправить.'
      : '✨ Գրեք ձեր բառերով՝ ինչ է արվել 3 ամսում, և ավելացրեք նկարներ — համակարգը ինքը կբաժանի տեքստը սլայդների, կգտնի թվերը, կկառուցի գծապատկերը և կընտրի նկարները: Հետո ամեն ինչ կարելի է ուղղել:' }),
    h('p', { class: 'small muted', text: L
      ? 'Или соберите слайды вручную (обложка, цифры, график, таблица, картинка, файлы), добавьте свои файлы и выгрузите '
        + 'в PDF или редактируемый PowerPoint.'
      : 'Հավաքեք սլայդները (շապիկ, թվեր, գծապատկեր, աղյուսակ, նկար, ֆայլեր), ավելացրեք ձեր ֆայլերը և '
        + 'արտահանեք PDF կամ խմբագրելի PowerPoint:' })));
  if (!decks.length) box.append(emptyBox(L ? 'Отчётов пока нет' : 'Հաշվետվություններ դեռ չկան', '📈'));
  const grid = h('div', { class: 'grid c2' });
  decks.forEach(d => grid.append(h('div', { class: 'card', style: 'margin:0' },
    h('div', { class: 'card-head' },
      h('h3', { style: 'margin:0', text: d.title }),
      h('div', { class: 'right' }, h('span', { class: 'badge plain', text: `${S.meta.quarters[d.quarter]} ${d.year}` }))),
    h('div', { class: 'small muted', text: `${d.client || '—'} · ${d.slides} ${L ? 'слайдов' : 'սլայդ'}` }),
    h('div', { class: 'row', style: 'margin-top:10px' },
      h('button', { class: 'btn sm primary', onClick: () => location.hash = `#/quarterly?id=${d.id}` }, '✏️ ' + t('btn.edit')),
      h('button', { class: 'btn sm', onClick: () => renderDeck(d.id, 'pdf', L) }, '📕 PDF'),
      h('button', { class: 'btn sm', onClick: () => renderDeck(d.id, 'pptx', L) }, '📙 PPTX'),
      h('button', { class: 'btn sm', onClick: () => window.open(`/print/quarterly/${d.id}`, '_blank') }, '🖨'),
      h('button', { class: 'btn sm danger', onClick: async () => {
        if (!await confirmDlg(L ? `Удалить «${d.title}»?` : `Ջնջե՞լ «${d.title}»-ը:`)) return;
        await api(`/api/quarterly/${d.id}`, { method: 'DELETE' });
        toast(t('msg.deleted'));
        window.MM.reload();
      } }, '🗑')))));
  box.append(grid);
  return box;
}

function newDeck(L) {
  const title = h('input', { type: 'text', value: L ? 'Квартальный отчёт' : 'Եռամսյակային հաշվետվություն' });
  const client = h('input', { type: 'text', placeholder: t('word.client') });
  const q = h('select', {}, ...[1, 2, 3, 4].map(i => h('option', { value: i,
    selected: i === Math.floor(new Date().getMonth() / 3) + 1 }, S.meta.quarters[i])));
  const year = h('input', { type: 'number', value: new Date().getFullYear() });
  const author = h('input', { type: 'text', placeholder: L ? 'Кто составил' : 'Ով է կազմել', value: S.user?.name || '' });
  const photo = photoButton({ section: 'Quarterly report cover', cls: 'btn sm',
    fields: [{ key: 'title', label: 'Report title' }, { key: 'client', label: 'Customer (client) name' },
      { key: 'quarter', type: 'enum', options: ['1', '2', '3', '4'], label: 'Quarter number (1-4)' },
      { key: 'year', type: 'number', label: 'Year' }],
    onResult: res => { const v = res.values || {}; setField(title, v.title); setField(client, v.client); setField(q, v.quarter); setField(year, v.year); } });
  modal({ title: '➕ ' + (L ? 'Новый отчёт' : 'Նոր հաշվետվություն'),
    body: h('div', {}, h('div', { class: 'row', style: 'justify-content:flex-end;margin-bottom:6px' }, photo),
      field(L ? 'Название' : 'Վերնագիր', title), field(t('word.client'), client),
      h('div', { class: 'grid c2' }, field(L ? 'Квартал' : 'Եռամսյակ', q), field(L ? 'Год' : 'Տարի', year)),
      field(L ? 'Автор' : 'Հեղինակ', author)),
    actions: [{ label: t('btn.cancel') }, { label: t('btn.create'), primary: true, onClick: async () => {
      const d = await api('/api/quarterly', { method: 'POST', body: { title: title.value, client: client.value,
        quarter: Number(q.value), year: Number(year.value), author: author.value } });
      location.hash = `#/quarterly?id=${d.id}`;
    } }] });
}

async function renderDeck(id, fmt, L) {
  loader(true, L ? 'Собираю файл…' : 'Հավաքում եմ ֆայլը…');
  try {
    const r = await api(`/api/quarterly/${id}/render?fmt=${fmt}`, { method: 'POST', body: {} });
    modal({ title: fmt === 'pptx' ? '📙 PowerPoint' : '📕 PDF', body: filesResult(r.files) });
  } finally { loader(false); }
}

/* ================================================================ խմբագրիչ */
function editor(deck, L) {
  let cur = 0;
  const root = h('div');
  const slidesCol = h('div');
  const editCol = h('div');
  const statusBadge = h('span', { class: 'badge ok', text: t('msg.saved') });

  const save = debounce(async () => {
    statusBadge.textContent = '…';
    statusBadge.className = 'badge warn';
    try {
      await api(`/api/quarterly/${deck.id}`, { method: 'PUT', body: deck, quiet: true });
      statusBadge.textContent = t('msg.saved');
      statusBadge.className = 'badge ok';
    } catch (e) {
      statusBadge.textContent = '⚠️ ' + e.message;
      statusBadge.className = 'badge err';
    }
  }, 600);

  // --- վերնագիր
  const head = h('div', { class: 'card' });
  const title = h('input', { type: 'text', value: deck.title });
  const client = h('input', { type: 'text', value: deck.client });
  const q = h('select', {}, ...[1, 2, 3, 4].map(i => h('option', { value: i, selected: i === deck.quarter }, S.meta.quarters[i])));
  const year = h('input', { type: 'number', value: deck.year });
  [title, client, q, year].forEach(i => i.addEventListener('input', () => {
    deck.title = title.value; deck.client = client.value;
    deck.quarter = Number(q.value); deck.year = Number(year.value); save();
  }));
  q.addEventListener('change', () => { deck.quarter = Number(q.value); save(); });
  head.append(h('div', { class: 'card-head' },
    h('button', { class: 'btn sm ghost', onClick: () => location.hash = '#/quarterly' }, '← ' + t('btn.back')),
    h('h2', { style: 'margin:0', text: '📈 ' + (L ? 'Редактор отчёта' : 'Հաշվետվության խմբագրիչ') }),
    h('div', { class: 'right' }, statusBadge,
      h('button', { class: 'btn sm primary', onClick: () => autoDialog(deck, L) }, '✨ ' + (L ? 'Авто-слайды' : 'Ավտո-սլայդներ')),
      h('button', { class: 'btn sm', onClick: () => filesDlg(deck, L, redraw) }, '📎 ' + t('word.files')),
      h('button', { class: 'btn sm', onClick: () => renderDeck(deck.id, 'pdf', L) }, '📕 PDF'),
      h('button', { class: 'btn sm', onClick: () => renderDeck(deck.id, 'pptx', L) }, '📙 PPTX'),
      h('button', { class: 'btn sm primary', onClick: () => window.open(`/print/quarterly/${deck.id}`, '_blank') }, '🖨 ' + t('btn.print')))),
    h('div', { class: 'grid c4' }, field(L ? 'Название' : 'Վերնագիր', title), field(t('word.client'), client),
      field(L ? 'Квартал' : 'Եռամսյակ', q), field(L ? 'Год' : 'Տարի', year)));

  function redraw() {
    // --- սլայդների ցանկ
    clear(slidesCol);
    const addBtn = h('button', { class: 'btn sm primary block' }, '➕ ' + (L ? 'Слайд' : 'Սլայդ'));
    addBtn.addEventListener('click', () => addSlideDlg(deck, L, i => { cur = i; save(); redraw(); }));
    slidesCol.append(h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h3', { style: 'margin:0', text: `${L ? 'Слайды' : 'Սլայդներ'} (${deck.slides.length})` })),
      h('div', { class: 'scroll' }, ...deck.slides.map((s, i) => {
        const mini = h('div', { class: 'slide-mini' + (i === cur ? ' active' : ''), style: 'margin-bottom:7px' },
          h('div', { class: 'sn', text: String(i + 1) }),
          h('div', { class: 'st' }, h('b', { text: s.title || S.meta.slide_names[s.type] }),
            h('span', { text: `${TYPE_IC[s.type] || '•'} ${S.meta.slide_names[s.type]}` })),
          h('div', { class: 'row tight' },
            h('button', { class: 'btn sm ghost', title: '↑', onClick: e => { e.stopPropagation(); move(i, -1); } }, '↑'),
            h('button', { class: 'btn sm ghost', title: '↓', onClick: e => { e.stopPropagation(); move(i, 1); } }, '↓'),
            h('button', { class: 'btn sm ghost', title: t('btn.delete'), onClick: async e => {
              e.stopPropagation();
              if (!await confirmDlg(L ? 'Удалить слайд?' : 'Ջնջե՞լ սլայդը:')) return;
              deck.slides.splice(i, 1); cur = Math.max(0, cur - (i <= cur ? 1 : 0)); save(); redraw();
            } }, '🗑')));
        mini.addEventListener('click', () => { cur = i; redraw(); });
        return mini;
      })), addBtn));
    // --- ընթացիկ սլայդը
    clear(editCol);
    if (!deck.slides.length) { editCol.append(h('div', { class: 'card' }, emptyBox(L ? 'Добавьте слайд' : 'Ավելացրեք սլայդ', '➕'))); return; }
    cur = Math.min(cur, deck.slides.length - 1);
    editCol.append(slideEditor(deck, cur, L, save, redraw));
  }
  function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= deck.slides.length) return;
    [deck.slides[i], deck.slides[j]] = [deck.slides[j], deck.slides[i]];
    cur = j; save(); redraw();
  }
  redraw();
  root.append(head, h('div', { class: 'grid', style: 'grid-template-columns:minmax(230px,300px) 1fr;align-items:start' },
    slidesCol, editCol));
  return root;
}

function addSlideDlg(deck, L, after) {
  let m;
  const grid = h('div', { class: 'grid c3' }, ...TYPES.map(ty => h('button', { class: 'pick', onClick: () => {
    deck.slides.push(blank(ty, deck, L));
    after(deck.slides.length - 1);
    if (m) m.close();
  } }, h('div', { class: 'pico' }, TYPE_IC[ty]), h('div', {}, h('div', { class: 'pt', text: S.meta.slide_names[ty] })))));
  m = modal({ title: '➕ ' + (L ? 'Тип слайда' : 'Սլայդի տեսակը'), wide: true, body: grid });
}

function blank(type, deck, L) {
  const s = { type, title: '', subtitle: '', body: '', caption: '', items: [], image: '', unit: '', head: [], rows: [], images: [] };
  if (type === 'gallery') s.title = L ? 'Фотоотчёт' : 'Ֆոտոշարք';
  if (type === 'cover') { s.title = deck.title; s.subtitle = deck.client; }
  if (type === 'metrics') { s.title = L ? 'Основные цифры' : 'Հիմնական թվերը';
    s.items = [{ label: L ? 'Выходы' : 'Հեռարձակումներ', value: '0', note: 'սփոթ' }]; }
  if (type === 'chart') { s.title = L ? 'Динамика' : 'Դինամիկա'; s.items = []; }
  if (type === 'bullets') { s.title = L ? 'Результаты' : 'Արդյունքներ'; s.items = ['']; }
  if (type === 'table') { s.title = L ? 'Таблица' : 'Աղյուսակ'; s.head = [L ? 'Показатель' : 'Ցուցանիշ', L ? 'Значение' : 'Արժեք']; }
  if (type === 'closing') { s.title = L ? 'Спасибо' : 'Շնորհակալություն'; }
  if (type === 'files') { s.title = L ? 'Приложенные файлы' : 'Կցված ֆայլեր'; }
  return s;
}

/* ---------------------------------------------------------------- սլայդի խմբագրիչ */
function slideEditor(deck, idx, L, save, redraw) {
  const s = deck.slides[idx];
  const card = h('div', { class: 'card' });
  const preview = h('div');
  const upd = () => { save(); clear(preview).append(slidePreview(s, deck, L)); };

  const inp = (label, key, { ta = false, rows = 3, hint = '' } = {}) => {
    const el = ta ? h('textarea', { rows: String(rows) }) : h('input', { type: 'text' });
    el.value = s[key] || '';
    el.addEventListener('input', () => { s[key] = el.value; upd(); });
    return field(label, el, { hint });
  };
  card.append(h('div', { class: 'card-head' },
    h('h3', { style: 'margin:0', text: `${TYPE_IC[s.type]} ${S.meta.slide_names[s.type]} · ${L ? 'слайд' : 'սլայդ'} ${idx + 1}` }),
    h('div', { class: 'right' },
      h('select', { onChange: e => { deck.slides[idx] = { ...blank(e.target.value, deck, L), title: s.title }; save(); redraw(); } },
        ...TYPES.map(ty => h('option', { value: ty, selected: ty === s.type }, S.meta.slide_names[ty]))))));

  // 📷 սլայդի բովանդակությունը լուսանկարից/ֆայլից (թվեր, աղյուսակ, կետեր, տեքստ)
  const SLIDE_PHOTO = {
    metrics: [{ key: 'rows', type: 'table', label: 'Key figures as rows [label, value, note]', hint: 'e.g. ["Broadcasts", "21 560", "spots"]' }],
    chart: [{ key: 'rows', type: 'table', label: 'Chart data as rows [label, value]', hint: 'one row per period/category; value — a number' }],
    table: [{ key: 'head', type: 'list', label: 'Table column headers' }, { key: 'rows', type: 'table', label: 'Table rows (cells)' }],
    bullets: [{ key: 'items', type: 'list', label: 'Bullet points / list items' }],
    text: [{ key: 'title', label: 'Heading' }, { key: 'body', type: 'text', label: 'Main text' }],
    closing: [{ key: 'body', type: 'text', label: 'Text' }],
  };
  if (SLIDE_PHOTO[s.type]) {
    card.append(h('div', { class: 'row', style: 'justify-content:flex-end;margin:-6px 0 6px' }, photoButton({
      section: `Report slide: ${s.type}`, cls: 'btn sm', fields: SLIDE_PHOTO[s.type],
      onResult: res => {
        const v = res.values || {};
        if (s.type === 'metrics' || s.type === 'chart') {
          s.items = (v.rows || []).map(r => ({ label: r[0] || '', value: r[1] || '', note: r[2] || '' }));
        } else if (s.type === 'table') {
          if (v.head?.length) s.head = v.head;
          if (v.rows?.length) s.rows = v.rows;
        } else if (s.type === 'bullets') {
          if (v.items?.length) s.items = v.items;
        } else {
          if (v.title) s.title = v.title;
          if (v.body) s.body = v.body;
        }
        save(); redraw();
      } })));
  }
  card.append(inp(L ? 'Заголовок' : 'Վերնագիր', 'title'));
  if (['cover', 'text'].includes(s.type)) card.append(inp(L ? 'Подзаголовок' : 'Ենթավերնագիր', 'subtitle'));
  if (['text', 'closing', 'photo_text'].includes(s.type)) card.append(inp(L ? 'Текст' : 'Տեքստ', 'body', { ta: true, rows: 7,
    hint: s.type === 'photo_text' ? (L ? 'Или пункты ниже — тогда текст не показывается' : 'Կամ կետերը ներքևում') : '' }));
  if (s.type === 'photo_text') {
    const ta = h('textarea', { rows: '5' });
    ta.value = (s.items || []).join('\n');
    ta.addEventListener('input', () => { s.items = ta.value.split(/[\r\n]+/).map(x => x.trim()).filter(Boolean); upd(); });
    card.append(field(L ? 'Пункты (каждый с новой строки)' : 'Կետերը (յուրաքանչյուրը նոր տողից)', ta));
  }
  if (s.type === 'gallery') {
    const images = (deck.attachments || []).filter(a => a.kind === 'image');
    const chosen = new Set((s.images || []).map(i => i.path));
    const grid = h('div', { class: 'grid c3' }, ...images.map(a => {
      const cb = h('input', { type: 'checkbox', checked: chosen.has(a.path) });
      cb.addEventListener('change', () => {
        if (cb.checked && chosen.size >= 6) { cb.checked = false; toast(L ? 'Максимум 6 фото на слайд' : 'Առավելագույնը 6 նկար', 'warn'); return; }
        cb.checked ? chosen.add(a.path) : chosen.delete(a.path);
        s.images = images.filter(x => chosen.has(x.path)).map(x => ({ path: x.path, caption: x.caption || '' }));
        upd();
      });
      return h('label', { class: 'li', style: 'cursor:pointer' }, cb,
        h('img', { src: `/api/quarterly/${deck.id}/media?path=${encodeURIComponent(a.path)}`, style: 'width:54px;height:40px;object-fit:cover;border-radius:6px' }),
        h('div', { class: 't' }, h('div', { class: 's', text: a.caption || a.name })));
    }));
    card.append(field(L ? 'Фото (до 6)' : 'Նկարներ (մինչև 6)', images.length ? grid : emptyBox(L ? 'Добавьте фото кнопкой 📎' : 'Ավելացրեք նկարներ 📎 կոճակով', '🖼')));
  }

  if (s.type === 'bullets') {
    const ta = h('textarea', { rows: '8' });
    ta.value = (s.items || []).join('\n');
    ta.addEventListener('input', () => { s.items = ta.value.split(/[\r\n]+/).map(x => x.trim()).filter(Boolean); upd(); });
    card.append(field(L ? 'Пункты (каждый с новой строки)' : 'Կետերը (յուրաքանչյուրը նոր տողից)', ta));
  }
  if (s.type === 'metrics' || s.type === 'chart') {
    const ta = h('textarea', { rows: '8' });
    ta.value = (s.items || []).map(i => [i.label, i.value, i.note].filter(x => x !== '' && x !== undefined).join('; ')).join('\n');
    ta.addEventListener('input', () => {
      s.items = ta.value.split(/[\r\n]+/).map(line => {
        const p = line.split(';').map(x => x.trim());
        return p[0] || p[1] ? { label: p[0] || '', value: p[1] || '', note: p[2] || '' } : null;
      }).filter(Boolean);
      upd();
    });
    card.append(field(L ? 'Строки: Название; Значение; Примечание' : 'Տողերը՝ Անվանում; Արժեք; Նշում', ta,
      { hint: L ? 'Например: Выходы; 21 560; спот' : 'Օրինակ՝ Հեռարձակումներ; 21 560; սփոթ' }));
    if (s.type === 'chart') card.append(inp(L ? 'Единица (подпись)' : 'Միավոր (ստորագրություն)', 'unit'));
    const imp = h('input', { type: 'file', accept: '.xlsx,.xlsm,.csv', style: 'display:none' });
    const impBtn = h('button', { class: 'btn sm' }, '📥 ' + (L ? 'Импорт цифр из файла (АКТ)' : 'Ներմուծել թվերը ֆայլից (ԱԿՏ)'));
    impBtn.addEventListener('click', () => imp.click());
    imp.addEventListener('change', async () => {
      if (!imp.files.length) return;
      const fd = new FormData(); fd.append('file', imp.files[0]);
      loader(true, L ? 'Считаю…' : 'Հաշվում եմ…');
      try {
        const r = await api('/api/quarterly/import', { method: 'POST', form: fd });
        s.items = s.type === 'chart' ? r.chart : r.metrics;
        if (!s.title) s.title = r.period;
        ta.value = s.items.map(i => [i.label, i.value, i.note].filter(Boolean).join('; ')).join('\n');
        toast(`✅ ${r.period}`); upd();
      } finally { loader(false); imp.value = ''; }
    });
    card.append(h('div', { class: 'row' }, impBtn, imp));
  }
  if (s.type === 'table') {
    const head = h('input', { type: 'text', value: (s.head || []).join('; ') });
    head.addEventListener('input', () => { s.head = head.value.split(';').map(x => x.trim()).filter(Boolean); upd(); });
    const rows = h('textarea', { rows: '8' });
    rows.value = (s.rows || []).map(r => r.join('; ')).join('\n');
    rows.addEventListener('input', () => {
      s.rows = rows.value.split(/[\r\n]+/).filter(x => x.trim())
        .map(line => line.split(';').map(c => c.trim()));
      upd();
    });
    card.append(field(L ? 'Заголовки через ;' : 'Վերնագրերը՝ ; նշանով', head),
      field(L ? 'Строки (ячейки через ;)' : 'Տողերը (վանդակները՝ ; նշանով)', rows));
  }
  if (s.type === 'image' || s.type === 'photo_text') {
    const images = (deck.attachments || []).filter(a => a.kind === 'image');
    const sel = h('select', {}, h('option', { value: '' }, '— ' + (L ? 'выберите картинку' : 'ընտրեք նկարը') + ' —'),
      ...images.map(a => h('option', { value: a.path, selected: a.path === s.image }, a.name)));
    sel.addEventListener('change', () => { s.image = sel.value; upd(); });
    card.append(field(L ? 'Картинка (из ваших файлов)' : 'Նկար (ձեր ֆայլերից)', sel,
      { hint: images.length ? '' : (L ? 'Сначала добавьте файлы кнопкой 📎 Файлы' : 'Նախ ավելացրեք ֆայլեր 📎 կոճակով') }),
    inp(L ? 'Подпись' : 'Ստորագրություն', 'caption'));
  }
  if (s.type === 'files') {
    const ta = h('textarea', { rows: '5' });
    ta.value = (s.items || []).join('\n');
    ta.addEventListener('input', () => { s.items = ta.value.split(/[\r\n]+/).map(x => x.trim()).filter(Boolean); upd(); });
    card.append(field(L ? 'Список (пусто = все приложенные файлы)' : 'Ցուցակ (դատարկ՝ բոլոր կցված ֆայլերը)', ta));
  }
  clear(preview).append(slidePreview(s, deck, L));
  return h('div', {}, card, h('div', { class: 'card' },
    h('h3', { text: '👁 ' + (L ? 'Предпросмотр' : 'Նախադիտում') }), preview));
}

function slidePreview(s, deck, L) {
  const dark = s.type === 'cover' || s.type === 'closing';
  const box = h('div', { class: 'preview' + (dark ? ' dark' : '') });
  box.append(h('div', { class: 'pk', text: dark ? `${S.meta.quarters[deck.quarter]} ${deck.year}` : S.meta.slide_names[s.type] }));
  box.append(h('h4', { text: s.title || S.meta.slide_names[s.type] }));
  if (s.subtitle) box.append(h('div', { class: 'small', style: 'opacity:.8', text: s.subtitle }));
  if (s.type === 'metrics') box.append(h('div', { class: 'pgrid' }, ...(s.items || []).slice(0, 8).map(i =>
    h('div', { class: 'pm' }, h('div', { class: 'pv', text: i.value || '—' }), h('div', { class: 'pl', text: i.label })))));
  if (s.type === 'chart') {
    const vals = (s.items || []).map(i => Number(String(i.value).replace(/[^\d.-]/g, '')) || 0);
    const max = Math.max(...vals, 1);
    box.append(h('div', { class: 'pbars' }, ...vals.slice(0, 24).map(v =>
      h('i', { style: `height:${Math.max(2, (v / max) * 100)}%` }))));
  }
  if (s.type === 'bullets') box.append(h('ul', { class: 'small', style: 'margin:6px 0 0;padding-left:18px' },
    ...(s.items || []).slice(0, 8).filter(Boolean).map(x => h('li', { text: x }))));
  if (s.type === 'text' || s.type === 'closing') box.append(h('p', { class: 'small',
    text: (s.body || '').slice(0, 420) }));
  if (s.type === 'photo_text') {
    const left = (s.items || []).length
      ? h('ul', { class: 'small', style: 'margin:6px 0 0;padding-left:18px' }, ...s.items.slice(0, 6).map(x => h('li', { text: x })))
      : h('p', { class: 'small', text: (s.body || '').slice(0, 300) });
    box.append(h('div', { style: 'display:flex;gap:10px;align-items:flex-start' }, h('div', { style: 'flex:1' }, left),
      s.image ? h('img', { src: `/api/quarterly/${deck.id}/media?path=${encodeURIComponent(s.image)}`, style: 'width:46%;max-height:160px;object-fit:cover;border-radius:8px' }) : null));
  }
  if (s.type === 'gallery') box.append(h('div', { style: 'display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px' },
    ...(s.images || []).map(i => h('img', { src: `/api/quarterly/${deck.id}/media?path=${encodeURIComponent(i.path)}`, style: 'width:100%;height:70px;object-fit:cover;border-radius:6px' }))));
  if (s.type === 'table') {
    const head = s.head?.length ? s.head : (s.rows?.[0] || []);
    const rows = s.head?.length ? (s.rows || []) : (s.rows || []).slice(1);
    box.append(h('table', { class: 'table', style: 'font-size:10px;margin-top:6px' },
      h('thead', {}, h('tr', {}, ...head.map(x => h('th', { text: x })))),
      h('tbody', {}, ...rows.slice(0, 5).map(r => h('tr', {}, ...r.map(c => h('td', { text: c })))))));
  }
  if (s.type === 'image') {
    if (s.image) box.append(h('img', { src: `/api/quarterly/${deck.id}/media?path=${encodeURIComponent(s.image)}`,
      style: 'max-height:62%;border-radius:8px;margin-top:8px' }));
    else box.append(h('div', { class: 'small muted', text: L ? 'Картинка не выбрана' : 'Նկարը ընտրված չէ' }));
  }
  if (s.type === 'files') {
    const names = (s.items?.length ? s.items : (deck.attachments || []).map(a => a.name));
    box.append(h('ul', { class: 'small', style: 'margin:6px 0 0;padding-left:18px' },
      ...names.slice(0, 7).map(n => h('li', { text: n }))));
  }
  return box;
}

/* ---------------------------------------------------------------- ֆայլեր */
function filesDlg(deck, L, after) {
  const list = h('div');
  const inp = h('input', { type: 'file', multiple: true, style: 'display:none' });
  const zone = h('div', { class: 'dropzone' }, h('div', { class: 'dzi' }, '📎'),
    h('div', { text: L ? 'Нажмите или перетащите свои файлы' : 'Սեղմեք կամ քաշեք ձեր ֆայլերը' }),
    h('div', { class: 'tiny muted', text: L ? 'Картинки можно вставить в слайд, остальные — в список файлов'
      : 'Նկարները կարելի է դնել սլայդում, մնացածը՝ ֆայլերի ցանկում' }));
  const draw = () => {
    clear(list);
    if (!deck.attachments.length) { list.append(emptyBox(L ? 'Файлов нет' : 'Ֆայլեր չկան', '📎')); return; }
    deck.attachments.forEach(a => list.append(h('div', { class: 'li' },
      h('span', { style: 'font-size:18px', text: a.kind === 'image' ? '🖼' : '📄' }),
      h('div', { class: 't' }, h('b', { text: a.name }), h('div', { class: 's', text: bytes(a.size) }),
        a.kind === 'image' ? captionInput(deck, a, L) : null),
      h('a', { class: 'btn sm', href: `/api/quarterly/${deck.id}/media?path=${encodeURIComponent(a.path)}`, target: '_blank' }, '👁'),
      h('button', { class: 'btn sm danger', onClick: async () => {
        const d = await api(`/api/quarterly/${deck.id}/attach?path=${encodeURIComponent(a.path)}`, { method: 'DELETE' });
        deck.attachments = d.attachments; draw(); after();
      } }, '🗑'))));
  };
  const upload = async files => {
    const fd = new FormData();
    [...files].forEach(f => fd.append('files', f));
    loader(true, L ? 'Загружаю…' : 'Բեռնում եմ…');
    try {
      const r = await api(`/api/quarterly/${deck.id}/attach`, { method: 'POST', form: fd });
      deck.attachments = r.deck.attachments;
      toast(`✅ ${r.attachments.length}`); draw(); after();
    } finally { loader(false); }
  };
  zone.addEventListener('click', () => inp.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('over'));
  zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('over'); upload(e.dataTransfer.files); });
  inp.addEventListener('change', () => inp.files.length && upload(inp.files));
  draw();
  modal({ title: '📎 ' + (L ? 'Мои файлы' : 'Իմ ֆայլերը'), wide: true,
    body: h('div', {}, zone, inp, h('div', { class: 'hr' }), h('div', { class: 'list' }, list)) });
}

/* ---------------------------------------------------------------- 📝 նկարի ստորագրություն (ավտո-ընտրության համար) */
function captionInput(deck, a, L) {
  const inp = h('input', { type: 'text', value: a.caption || '', style: 'margin-top:4px;height:30px',
    placeholder: L ? 'Что на фото? (помогает подобрать к тексту)' : 'Ի՞նչ է նկարում (օգնում է ընտրել տեքստին)' });
  inp.addEventListener('input', debounce(async () => {
    a.caption = inp.value.trim();
    try { await api(`/api/quarterly/${deck.id}`, { method: 'PUT', body: { attachments: deck.attachments }, quiet: true }); }
    catch (e) { /* */ }
  }, 600));
  return inp;
}

/* ---------------------------------------------------------------- ✨ ավտո-պրեզենտացիա (NotebookLM-ի նման) */
const EXAMPLE = {
  ru: 'Например:\nОктябрь:\n- подключили 15 новых магазинов сети Ереван Сити\n- запустили рекламу Coca-Cola на 120 адресах, 12 000 выходов\n\nНоябрь: установили новое оборудование в 30 точках, 15 500 выходов.\n\nДекабрь: новогодняя кампания для SAS, 18 000 выходов, выполнение плана 98%.\n\nИтоги: всего 45 500 выходов, 8 новых клиентов.\n\nПланы на следующий квартал:\n- подключить новую сеть\n- перейти на новые плееры',
  hy: 'Օրինակ՝\nՀոկտեմբեր՝\n- միացրինք 15 նոր խանութ\n- գործարկեցինք գովազդը 120 հասցեում, 12 000 սփոթ\n\nՆոյեմբերին տեղադրեցինք նոր սարքեր 30 կետում, 15 500 սփոթ:\n\nԴեկտեմբեր՝ ամանորյա արշավ, 18 000 սփոթ, պլանի կատարում 98%:\n\nԱմփոփում՝ ընդամենը 45 500 սփոթ, 8 նոր հաճախորդ:\n\nՀաջորդ եռամսյակի պլանները՝\n- միացնել նոր ցանց',
};

function autoDialog(deck, L) {
  const isNew = !deck;
  const title = h('input', { type: 'text', value: deck?.title || (L ? 'Квартальный отчёт' : 'Եռամսյակային հաշվետվություն') });
  const client = h('input', { type: 'text', value: deck?.client || '', placeholder: t('word.client') });
  const qNow = Math.floor(new Date().getMonth() / 3) + 1;
  const q = h('select', {}, ...[1, 2, 3, 4].map(i => h('option', { value: i, selected: i === (deck?.quarter || qNow) }, S.meta.quarters[i])));
  const year = h('input', { type: 'number', value: deck?.year || new Date().getFullYear() });
  const prompt = h('textarea', { rows: '12', placeholder: EXAMPLE[L ? 'ru' : 'hy'] });
  prompt.value = deck?.prompt || '';
  const files = [];
  const list = h('div', { class: 'tiny muted' });
  const inp = h('input', { type: 'file', multiple: true, accept: 'image/*', style: 'display:none' });
  const drawList = () => {
    const had = (deck?.attachments || []).filter(a => a.kind === 'image').length;
    list.textContent = (files.length ? `📷 ${files.length} ${L ? 'новых фото' : 'նոր նկար'}: ${files.map(f => f.name).slice(0, 6).join(', ')}${files.length > 6 ? '…' : ''}` : '')
      + (had ? `  ·  ${had} ${L ? 'фото уже в отчёте' : 'նկար արդեն կա'}` : '');
  };
  const zone = h('div', { class: 'dropzone' }, h('div', { class: 'dzi' }, '📷'),
    h('div', { text: L ? 'Фото за квартал — нажмите или перетащите' : 'Եռամսյակի նկարները՝ սեղմեք կամ քաշեք' }),
    h('div', { class: 'tiny muted', text: L ? 'Система сама подберёт фото к тексту (по подписи, дате съёмки и тексту на фото). Лишние попадут в «Фотоотчёт».'
      : 'Համակարգը ինքը կընտրի նկարը տեքստին (ստորագրությամբ, նկարահանման ամսաթվով, նկարի վրայի տեքստով):' }));
  zone.addEventListener('click', () => inp.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('over'));
  zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('over'); files.push(...[...e.dataTransfer.files].filter(f => f.type.startsWith('image/'))); drawList(); });
  inp.addEventListener('change', () => { files.push(...inp.files); inp.value = ''; drawList(); });
  drawList();
  const ai = S.meta.extract?.local_ai || {};
  const useAi = h('input', { type: 'checkbox', checked: true, disabled: !ai.ready });
  const append = h('input', { type: 'checkbox' });
  modal({ title: '✨ ' + (L ? 'Отчёт из текста и фото' : 'Հաշվետվություն տեքստից և նկարներից'), wide: true,
    body: h('div', {},
      isNew ? h('div', { class: 'grid c4' }, field(L ? 'Название' : 'Վերնագիր', title), field(t('word.client'), client),
        field(L ? 'Квартал' : 'Եռամսյակ', q), field(L ? 'Год' : 'Տարի', year)) : null,
      field(L ? 'Что сделано за квартал — своими словами (по месяцам, цифры, итоги, планы)' : 'Ինչ է արվել եռամսյակում՝ ձեր բառերով (ամիսներ, թվեր, ամփոփում, պլաններ)', prompt,
        { hint: L ? 'Пишите как удобно: по месяцам («Октябрь: …»), списком «- …» или абзацами. Цифры («120 адресов», «98%») станут слайдом с цифрами и графиком.'
          : 'Գրեք ինչպես հարմար է՝ ամիսներով («Հոկտեմբեր՝ …»), ցուցակով «- …» կամ պարբերություններով: Թվերը կդառնան սլայդ և գծապատկեր:' }),
      zone, inp, list,
      h('div', { class: 'row', style: 'margin-top:10px;flex-wrap:wrap' },
        h('label', { class: 'row tight small' }, useAi, ai.ready ? `🧠 ${L ? 'Локальный ИИ' : 'Տեղային ԻԻ'} (${ai.model})`
          : (L ? '🧠 Локальный ИИ не установлен — работаю по правилам (install_local_ai.bat)' : '🧠 Տեղային ԻԻ չկա՝ աշխատում եմ կանոններով')),
        !isNew ? h('label', { class: 'row tight small' }, append, L ? 'Добавить к существующим слайдам (не заменять)' : 'Ավելացնել առկա սլայդներին') : null),
      h('p', { class: 'tiny muted', text: L ? '🔒 Всё делается на этом компьютере, без интернета и облака.' : '🔒 Ամեն ինչ արվում է այս համակարգչում՝ առանց ինտերնետի:' })),
    actions: [{ label: t('btn.cancel') }, { label: '✨ ' + (L ? 'Создать презентацию' : 'Ստեղծել պրեզենտացիա'), primary: true, onClick: async () => {
      if (prompt.value.trim().length < 20) { toast(L ? 'Опишите подробнее, что сделано' : 'Գրեք ավելի մանրամասն', 'err'); return false; }
      loader(true, L ? 'Собираю слайды и подбираю фото… (до 1–3 мин)' : 'Հավաքում եմ սլայդները և ընտրում նկարները…');
      try {
        let d = deck;
        if (isNew) d = await api('/api/quarterly', { method: 'POST', body: { title: title.value, client: client.value,
          quarter: Number(q.value), year: Number(year.value), author: S.user?.name || '', slides: [{ type: 'cover', title: title.value }] } });
        for (let k = 0; k < files.length; k += 8) {
          const fd = new FormData();
          files.slice(k, k + 8).forEach(f => fd.append('files', f));
          await api(`/api/quarterly/${d.id}/attach`, { method: 'POST', form: fd });
        }
        const r = await api(`/api/quarterly/${d.id}/auto`, { method: 'POST',
          body: { prompt: prompt.value, use_ai: useAi.checked, append: append.checked } });
        const i = r.info;
        toast(`✨ ${i.slides} ${L ? 'слайдов' : 'սլայդ'} · 📷 ${i.matched}/${i.photos} ${L ? 'фото подобрано к тексту' : 'նկար ընտրված'}${i.gallery ? ' · ' + i.gallery + (L ? ' в фотоотчёте' : ' ֆոտոշարքում') : ''} · ${i.engine === 'ollama' ? 'ИИ' : (L ? 'правила' : 'կանոններ')}`, 'ok');
        if (location.hash === `#/quarterly?id=${d.id}`) window.MM.reload(); else location.hash = `#/quarterly?id=${d.id}`;
      } catch (e) { return false; } finally { loader(false); }
    } }] });
}
