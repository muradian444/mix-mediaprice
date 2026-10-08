// ✏️ Խմբագրել պատրաստի ֆայլը՝ Word (պարբերություններ, աղյուսակներ), Excel/CSV (վանդակներ), TXT,
// PDF և լուսանկար (տեքստը դառնում է Word): Հավելվածում ստեղծված փաստաթուղթը բացվում է ՁԵՎՈՒՄ:
import { EDITABLE, S, api, bytes, clear, dt, emptyBox, fileIcon, filesResult, h, loader, modal, t, toast } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Загрузите готовый файл и измените его прямо здесь'
  : 'Բեռնեք պատրաստի ֆայլը և փոխեք այն հենց այստեղ';

const KIND_NAME = {
  contract: ['պայմանագրի ձևում', 'в форме договора'], plan: ['մեդիա պլանի ձևում', 'в мастере медиаплана'],
  act: ['ԱԿՏ-ի ձևում', 'в форме АКТа'], kp: ['ԿՊ-ի ձևում', 'в форме КП'],
};

export async function render(params) {
  const L = S.lang === 'ru' ? 1 : 0;
  let model = null;
  try {
    if (params.token) model = await api(`/api/edit/${encodeURIComponent(params.token)}`);
    else if (params.fid) {
      loader(true, L ? 'Открываю файл…' : 'Բացում եմ ֆայլը…');
      try { model = await api('/api/edit/open-file', { method: 'POST', body: { fid: params.fid } }); } finally { loader(false); }
    } else if (params.path) {
      loader(true, L ? 'Открываю файл…' : 'Բացում եմ ֆայլը…');
      try {
        model = await api('/api/edit/open-vault', { method: 'POST', body: { path: params.path, scope: params.scope || 'me' } });
      } finally { loader(false); }
    }
  } catch (e) { model = null; }
  if (model) {
    if (!params.token) history.replaceState(null, '', `#/editor?token=${encodeURIComponent(model.token)}`);
    return editorView(model, L);
  }
  return startView(L);
}

/* ---------------------------------------------------------------- սկիզբ՝ ֆայլի ընտրություն */
async function startView(L) {
  const root = h('div');
  const inp = h('input', { type: 'file', accept: (S.meta.edit_formats || EDITABLE.map(x => '.' + x)).join(','), style: 'display:none' });
  const zone = h('div', { class: 'dropzone big' }, h('div', { class: 'dzi' }, '✏️'),
    h('div', { style: 'font-weight:700', text: L ? 'Нажмите или перетащите готовый файл' : 'Սեղմեք կամ քաշեք պատրաստի ֆայլը' }),
    h('div', { class: 'tiny muted', text: L
      ? 'Word (.docx), Excel (.xlsx), CSV, TXT, PDF или фото документа. Оригинал не меняется — сохраняется новая версия в «Мой уголок».'
      : 'Word (.docx), Excel (.xlsx), CSV, TXT, PDF կամ փաստաթղթի նկար: Բնօրինակը չի փոխվում՝ նոր տարբերակը պահվում է «Իմ անկյունում»:' }));
  const open = async f => {
    const fd = new FormData();
    fd.append('file', f);
    loader(true, L ? 'Открываю файл… (фото и сканы — до 40 сек)' : 'Բացում եմ ֆայլը… (նկար/սկան՝ մինչև 40 վրկ)');
    try {
      const m = await api('/api/edit/open', { method: 'POST', form: fd });
      location.hash = `#/editor?token=${encodeURIComponent(m.token)}`;
    } catch (e) { /* toast */ } finally { loader(false); }
  };
  zone.addEventListener('click', () => inp.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('over'));
  zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('over'); if (e.dataTransfer.files.length) open(e.dataTransfer.files[0]); });
  inp.addEventListener('change', () => { if (inp.files.length) open(inp.files[0]); inp.value = ''; });
  root.append(h('div', { class: 'card' },
    h('h2', { text: '✏️ ' + (L ? 'Изменить готовый файл' : 'Խմբագրել պատրաստի ֆայլը') }), h('div', { class: 'gradline' }),
    zone, inp,
    h('div', { class: 'grid c3', style: 'margin-top:14px' },
      tip('📄', L ? 'Договор, созданный здесь' : 'Այստեղ ստեղծված պայմանագիր',
        L ? 'Откроется в форме договора: поменяйте поля и создайте заново' : 'Կբացվի պայմանագրի ձևում՝ փոխեք դաշտերը և ստեղծեք նորից'),
      tip('📊', L ? 'Медиаплан (PDF)' : 'Մեդիա պլան (PDF)',
        L ? 'Клиент, период, адреса и часы попадут в мастер медиаплана' : 'Պատվիրատուն, ժամանակահատվածը, հասցեները և ժամերը կլցվեն մեդիա պլանում'),
      tip('📝', L ? 'Любой Word / Excel / PDF / фото' : 'Ցանկացած Word / Excel / PDF / նկար',
        L ? 'Текст и таблицы правятся прямо на странице, оформление Word сохраняется' : 'Տեքստը և աղյուսակները փոխվում են էջում, Word-ի ձևավորումը պահպանվում է'))));
  let files = [];
  try { files = await api('/api/files?limit=40', { quiet: true }); } catch (e) { files = []; }
  files = files.filter(f => EDITABLE.includes(String(f.ext).toLowerCase()));
  const list = h('div', { class: 'list' });
  if (!files.length) list.append(emptyBox(L ? 'Вы ещё не создали документов' : 'Դեռ փաստաթղթեր չեք ստեղծել', '📄'));
  files.slice(0, 20).forEach(f => list.append(h('div', { class: 'li' },
    h('span', { style: 'font-size:18px', text: fileIcon(f.ext) }),
    h('div', { class: 't' }, h('b', { text: f.name }), h('div', { class: 's', text: `${dt(f.created)} · ${bytes(f.size)}` })),
    h('button', { class: 'btn sm primary', onClick: () => { location.hash = `#/editor?fid=${encodeURIComponent(f.id)}`; } },
      '✏️ ' + t('btn.edit')))));
  root.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' }, h('h3', { text: L ? 'Мои последние документы' : 'Իմ վերջին փաստաթղթերը' }),
      h('div', { class: 'right' }, h('button', { class: 'btn sm ghost', dataset: { go: 'vault' } }, '👤 ' + t('sec.vault')))),
    list));
  return root;
}
const tip = (ic, title, text) => h('div', { class: 'tile plain' }, h('div', { style: 'font-size:20px', text: ic }),
  h('b', { text: title }), h('div', { class: 'tiny muted', text }));

/* ---------------------------------------------------------------- խմբագրիչ */
function editorView(m, L) {
  const root = h('div');
  const changed = new Map();          // DOCX՝ id -> {id, text|rows}
  const cellChanges = new Map();      // XLSX/CSV՝ "s:r:c" -> {s, r, c, v}
  let dirty = false;
  const status = h('span', { class: 'badge ok', text: L ? 'без изменений' : 'առանց փոփոխության' });
  const markDirty = () => {
    dirty = true;
    const n = m.type === 'sheet' ? cellChanges.size : (m.type === 'docx' ? changed.size : 1);
    status.textContent = `${L ? 'изменено' : 'փոփոխված'}: ${n}`;
    status.className = 'badge warn';
  };
  const name = h('input', { type: 'text', value: m.name.replace(/\.[^.]+$/, '') + (L ? '_изм' : '_փոփ'), style: 'max-width:280px' });
  const pdfCb = h('input', { type: 'checkbox', checked: !!S.meta.pdf?.ready });
  const result = h('div');
  const body = h('div');

  // ձևում բացելու առաջարկ
  const meta = m.meta;
  if (meta && KIND_NAME[meta.kind]) {
    root.append(h('div', { class: 'card notice' },
      h('div', { class: 'row' },
        h('span', { style: 'font-size:24px', text: '✨' }),
        h('div', { style: 'flex:1;min-width:220px' },
          h('b', { text: L ? 'Этот документ создан в приложении' : 'Այս փաստաթուղթը ստեղծվել է հավելվածում' }),
          h('div', { class: 'small muted', text: L
            ? `Можно открыть его ${KIND_NAME[meta.kind][1]}, поменять нужные поля и создать новый документ.`
            : `Կարելի է բացել այն ${KIND_NAME[meta.kind][0]}, փոխել դաշտերը և ստեղծել նոր փաստաթուղթ:` })),
        h('button', { class: 'btn primary', onClick: () => openInForm(meta) }, '✨ ' + (L ? 'Открыть в форме' : 'Բացել ձևում')))));
  }
  if (m.note === 'scan' || m.note === 'pdf') {
    root.append(h('div', { class: 'card notice warn' }, h('div', { class: 'small', text: '⚠️ ' + (m.note === 'scan'
      ? (L ? 'Текст распознан с фото/скана — проверьте его. Оформление упрощено, сохраняется как Word.'
        : 'Տեքստը ճանաչվել է նկարից/սկանից՝ ստուգեք: Ձևավորումը պարզեցված է, պահվում է Word-ով:')
      : (L ? 'Текст взят из PDF — оформление упрощено, сохраняется как Word (.docx).'
        : 'Տեքստը վերցվել է PDF-ից՝ ձևավորումը պարզեցված է, պահվում է Word-ով (.docx):')) })));
  }

  const findBtn = h('button', { class: 'btn', onClick: () => findReplace() }, '🔍 ' + (L ? 'Найти и заменить' : 'Գտնել և փոխարինել'));
  const save = h('button', { class: 'btn primary' }, '💾 ' + t('btn.save'));
  save.addEventListener('click', doSave);
  root.append(h('div', { class: 'card sticky-head' },
    h('div', { class: 'card-head', style: 'margin:0' },
      h('button', { class: 'btn sm ghost', onClick: () => { if (!dirty || confirm(L ? 'Выйти без сохранения?' : 'Դուրս գա՞լ առանց պահելու:')) location.hash = '#/editor'; } }, '← ' + t('btn.back')),
      h('div', { style: 'min-width:0' }, h('h2', { style: 'margin:0;word-break:break-all', text: `${fileIcon(m.ext)} ${m.name}` }),
        h('div', { class: 'tiny muted', text: m.type === 'docx' ? `${m.paragraphs} ${L ? 'абзацев' : 'պարբերություն'} · ${m.tables} ${L ? 'таблиц' : 'աղյուսակ'}`
          : m.type === 'sheet' ? `${m.sheets.length} ${L ? 'лист(а)' : 'թերթ'}` : '' })),
      h('div', { class: 'right' }, status,
        m.type !== 'empty' ? findBtn : null,
        h('a', { class: 'btn', href: `/api/edit/${encodeURIComponent(m.token)}/file?download=1` }, '⬇️'))),
    m.type !== 'empty' ? h('div', { class: 'row', style: 'margin-top:12px' },
      h('span', { class: 'small muted', text: L ? 'Сохранить как:' : 'Պահել որպես՝' }), name,
      m.type === 'docx' ? h('label', { class: 'check' }, pdfCb, L ? '+ PDF' : '+ PDF') : null,
      save) : null));
  root.append(body, result);

  if (m.type === 'docx') drawDocx();
  else if (m.type === 'sheet') drawSheet();
  else if (m.type === 'text') drawText();
  else body.append(h('div', { class: 'card' }, emptyBox(L
    ? 'В этом PDF нет текста (это скан). Включите распознавание фото в ⚙️ Настройках или загрузите Word-версию.'
    : 'Այս PDF-ում տեքստ չկա (սկան է): Միացրեք նկարի ճանաչումը ⚙️ Կարգավորումներում կամ բեռնեք Word տարբերակը:', '📄')));

  /* ---- DOCX ---- */
  function autosize(ta) { ta.style.height = 'auto'; ta.style.height = (ta.scrollHeight + 2) + 'px'; }
  function rowsFor(text) { return Math.max(1, String(text).split('\n').reduce((a, l) => a + Math.max(1, Math.ceil(l.length / 95)), 0)); }
  function drawDocx() {
    const page = h('div', { class: 'card docpage' });
    m.blocks.forEach(b => {
      if (b.t === 'p') {
        const ta = h('textarea', { class: `ep ${b.style || ''}`, rows: String(rowsFor(b.text)), spellcheck: 'false',
          placeholder: '¶', style: b.align ? `text-align:${b.align}` : null });
        ta.value = b.text;
        ta.dataset.id = b.id;
        ta.addEventListener('input', () => {
          b.text = ta.value;
          changed.set(b.id, { id: b.id, text: ta.value });
          autosize(ta);
          markDirty();
        });
        b.el = ta;
        page.append(ta);
      } else {
        const tbl = h('table', { class: 'etable' });
        b.cells = [];
        b.rows.forEach((row, r) => {
          const tr = h('tr');
          b.cells[r] = [];
          row.forEach((cell, c) => {
            const ta = h('textarea', { class: 'ec', rows: String(rowsFor(cell)), spellcheck: 'false' });
            ta.value = cell;
            ta.addEventListener('input', () => {
              b.rows[r][c] = ta.value;
              changed.set(b.id, { id: b.id, rows: b.rows });
              autosize(ta);
              markDirty();
            });
            b.cells[r][c] = ta;
            tr.append(h('td', {}, ta));
          });
          tbl.append(tr);
        });
        page.append(h('div', { class: 'tablewrap', style: 'margin:8px 0' }, tbl));
      }
    });
    body.append(page);
  }

  /* ---- XLSX/CSV ---- */
  let sheetIdx = 0;
  function drawSheet() {
    clear(body);
    const tabs = h('div', { class: 'seg', style: 'margin-bottom:10px;flex-wrap:wrap' },
      ...m.sheets.map((s, i) => h('button', { class: i === sheetIdx ? 'on' : '', onClick: () => { sheetIdx = i; drawSheet(); } }, s.name)));
    const sh = m.sheets[sheetIdx];
    const cols = Math.max(1, ...sh.rows.map(r => r.length));
    const tbl = h('table', { class: 'table sheet' });
    tbl.append(h('thead', {}, h('tr', {}, h('th', { text: '#' }), ...Array.from({ length: cols }, (_, c) => h('th', { text: colName(c) })))));
    const tb = h('tbody');
    sh.rows.forEach((row, r) => {
      const tr = h('tr', {}, h('th', { text: String(r + 1) }));
      for (let c = 0; c < cols; c++) {
        const td = h('td', { contenteditable: 'plaintext-only', spellcheck: 'false' });
        td.textContent = row[c] ?? '';
        td.addEventListener('input', () => {
          const v = td.innerText.replace(/\n$/, '');
          while (row.length <= c) row.push('');
          row[c] = v;
          cellChanges.set(`${sheetIdx}:${r}:${c}`, { s: sheetIdx, r, c, v });
          td.classList.add('chg');
          markDirty();
        });
        tr.append(td);
      }
      tb.append(tr);
    });
    tbl.append(tb);
    const addRow = h('button', { class: 'btn sm', onClick: () => { sh.rows.push(Array(cols).fill('')); drawSheet(); } },
      '➕ ' + (L ? 'Строка' : 'Տող'));
    body.append(h('div', { class: 'card' }, tabs,
      sh.total_rows > sh.rows.length ? h('div', { class: 'small', style: 'color:var(--warn);margin-bottom:8px',
        text: `⚠️ ${L ? 'Показаны первые' : 'Ցուցադրված են առաջին'} ${sh.rows.length} / ${sh.total_rows} ${L ? 'строк. Остальные сохраняются без изменений.' : 'տողերը: Մնացածը պահվում են անփոփոխ:'}` }) : null,
      h('div', { class: 'tablewrap sheetwrap' }, tbl), h('div', { class: 'row', style: 'margin-top:10px' }, addRow)));
  }
  const colName = c => { let s = ''; c += 1; while (c) { const m2 = (c - 1) % 26; s = String.fromCharCode(65 + m2) + s; c = Math.floor((c - 1) / 26); } return s; };

  /* ---- TXT ---- */
  let textArea = null;
  function drawText() {
    textArea = h('textarea', { rows: '24', class: 'mono', spellcheck: 'false' });
    textArea.value = m.text;
    textArea.addEventListener('input', markDirty);
    body.append(h('div', { class: 'card' }, textArea));
  }

  /* ---- գտնել / փոխարինել ---- */
  function findReplace() {
    const f = h('input', { type: 'text', placeholder: L ? 'Что найти' : 'Ինչ գտնել' });
    const r = h('input', { type: 'text', placeholder: L ? 'На что заменить' : 'Ինչով փոխարինել' });
    const cs = h('input', { type: 'checkbox' });
    const info = h('div', { class: 'small muted' });
    const count = () => {
      const needle = f.value;
      if (!needle) { info.textContent = ''; return; }
      const re = mkRe(needle, cs.checked);
      let n = 0;
      eachText(txt => { n += (txt.match(re) || []).length; return null; });
      info.textContent = `${L ? 'Найдено' : 'Գտնվեց'}: ${n}`;
    };
    f.addEventListener('input', count); cs.addEventListener('change', count);
    modal({ title: '🔍 ' + (L ? 'Найти и заменить' : 'Գտնել և փոխարինել'),
      body: h('div', {}, h('div', { class: 'field' }, f), h('div', { class: 'field' }, r),
        h('label', { class: 'check' }, cs, L ? 'Учитывать регистр' : 'Հաշվի առնել մեծատառերը'), info),
      actions: [{ label: t('btn.cancel') }, { label: L ? 'Заменить всё' : 'Փոխարինել բոլորը', primary: true, onClick: () => {
        if (!f.value) return false;
        const re = mkRe(f.value, cs.checked);
        let n = 0;
        eachText(txt => { const k = (txt.match(re) || []).length; if (!k) return null; n += k; return txt.replace(re, () => r.value); });
        toast(`${L ? 'Заменено' : 'Փոխարինվեց'}: ${n}`, n ? 'ok' : 'warn');
      } }] });
  }
  const mkRe = (s, caseSens) => new RegExp(s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), caseSens ? 'g' : 'gi');
  // fn(text) -> նոր տեքստ կամ null (առանց փոփոխության)
  function eachText(fn) {
    if (m.type === 'docx') {
      m.blocks.forEach(b => {
        if (b.t === 'p') {
          const nv = fn(b.text);
          if (nv !== null && nv !== b.text) { b.text = nv; b.el.value = nv; changed.set(b.id, { id: b.id, text: nv }); markDirty(); }
        } else {
          let any = false;
          b.rows.forEach((row, r) => row.forEach((cell, c) => {
            const nv = fn(cell);
            if (nv !== null && nv !== cell) { b.rows[r][c] = nv; if (b.cells?.[r]?.[c]) b.cells[r][c].value = nv; any = true; }
          }));
          if (any) { changed.set(b.id, { id: b.id, rows: b.rows }); markDirty(); }
        }
      });
    } else if (m.type === 'sheet') {
      m.sheets.forEach((sh, s) => sh.rows.forEach((row, r) => row.forEach((cell, c) => {
        const nv = fn(String(cell ?? ''));
        if (nv !== null && nv !== cell) { row[c] = nv; cellChanges.set(`${s}:${r}:${c}`, { s, r, c, v: nv }); markDirty(); }
      })));
      drawSheet();
    } else if (textArea) {
      const nv = fn(textArea.value);
      if (nv !== null && nv !== textArea.value) { textArea.value = nv; markDirty(); }
    }
  }

  /* ---- պահել ---- */
  async function doSave() {
    if (!dirty && !confirm(L ? 'Изменений нет. Всё равно сохранить копию?' : 'Փոփոխություն չկա: Միևնույն է պահե՞լ պատճենը:')) return;
    const payload = { name: name.value.trim(), pdf: pdfCb.checked };
    if (m.type === 'docx') payload.blocks = [...changed.values()];
    else if (m.type === 'sheet') payload.changes = [...cellChanges.values()];
    else payload.text = textArea.value;
    loader(true, L ? 'Сохраняю…' : 'Պահում եմ…');
    try {
      const r = await api(`/api/edit/${encodeURIComponent(m.token)}/save`, { method: 'POST', body: payload });
      changed.clear(); cellChanges.clear(); dirty = false;
      status.textContent = t('msg.saved'); status.className = 'badge ok';
      clear(result).append(filesResult(r.files, r.note));
      toast(`${t('msg.saved')} · ${L ? 'в «Мой уголок → Изменённые»' : '«Իմ անկյունը → Խմբագրված»'}`);
      result.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) { /* toast */ } finally { loader(false); }
  }
  return root;
}

/* ձևում բացել (պայմանագիր / մեդիա պլան / ԱԿՏ / ԿՊ) */
export function openInForm(meta) {
  if (meta.kind === 'contract') { S.prefill = { section: 'contracts', data: meta.data || {} }; location.hash = `#/contracts?kind=${encodeURIComponent(meta.flow || '')}`; }
  else if (meta.kind === 'plan') { S.prefill = { section: 'plan', data: meta.data || {} }; location.hash = '#/plan'; }
  else if (meta.kind === 'kp') { S.prefill = { section: 'kp', data: meta.data || {} }; location.hash = `#/kp?kind=${encodeURIComponent(meta.kp_kind || '1')}`; }
  else if (meta.kind === 'act') { S.prefill = { section: 'act', data: meta.data || {}, result: meta.result || null }; location.hash = '#/act'; }
}
