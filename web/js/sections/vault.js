// 👤 Իմ անկյունը՝ օգտատիրոջ բոլոր փաստաթղթերը (պայմանագրեր, մեդիա պլաններ, ԱԿՏ, ԿՊ, խմբագրված…)
// + ընդհանուր պահոց + (ադմինի համար) ուրիշների անկյունները: Թղթապանակներ, վերբեռնում, որոնում, խմբագրում, տպել
import { EDITABLE, S, api, bytes, clear, confirmDlg, debounce, dt, emptyBox, fileIcon, h, loader, modal,
  nf, promptDlg, t, toast } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Ваши договоры, медиапланы, АКТы и всё, что вы создали'
  : 'Ձեր պայմանագրերը, մեդիա պլանները, ԱԿՏ-երը և այն ամենը, ինչ ստեղծել եք';

let PATH = '';
let SCOPE = 'me';

const CAT_IC = { contract: '📄', plan: '📊', act: '🧾', kp: '💼', law: '⚖️', quarterly: '📈', voice: '🎙', edited: '✏️', other: '📁' };
const CAT_RU = { contract: 'Договоры', plan: 'Медиапланы', act: 'АКТы', kp: 'КП', law: 'Юрист', quarterly: 'Отчёты',
  voice: 'Голос', edited: 'Изменённые', other: 'Другое' };

export async function render(params) {
  const L = S.lang === 'ru' ? 1 : 0;
  if (params.path !== undefined) PATH = params.path;
  if (params.scope) SCOPE = params.scope;
  if (SCOPE.startsWith('u:') && S.user?.role !== 'admin') SCOPE = 'me';
  const root = h('div');
  const head = h('div');
  const crumbs = h('div', { class: 'crumbs' });
  const items = h('div');
  const statsBox = h('span', { class: 'tiny muted' });
  const q = h('input', { type: 'search', placeholder: (L ? 'Поиск файла…' : 'Որոնել ֆայլ…') });
  const qs = () => `scope=${encodeURIComponent(SCOPE)}`;
  const fileUrl = it => `/api/vault/file?path=${encodeURIComponent(it.path)}&${qs()}`;

  // ------------------------------------------------ պրոֆիլ + բաժիններ
  async function drawHead() {
    clear(head);
    let c;
    try { c = await api(`/api/vault/corner?${qs()}`, { quiet: true }); } catch (e) { return; }
    const p = c.profile || {};
    const tabs = h('div', { class: 'seg' },
      h('button', { class: SCOPE === 'me' ? 'on' : '', onClick: () => setScope('me') }, '👤 ' + (L ? 'Мои файлы' : 'Իմ ֆայլերը')),
      h('button', { class: SCOPE === 'shared' ? 'on' : '', onClick: () => setScope('shared') }, '🗂 ' + (L ? 'Общие' : 'Ընդհանուր')));
    let userSel = null;
    if (c.users?.length) {
      userSel = h('select', { style: 'width:auto;min-width:170px' },
        h('option', { value: '' }, L ? '👥 Уголок пользователя…' : '👥 Օգտատիրոջ անկյունը…'),
        ...c.users.filter(u => u.login !== S.user?.login).map(u =>
          h('option', { value: 'u:' + u.login, selected: SCOPE === 'u:' + u.login }, `${u.name} (${u.login})`)));
      userSel.addEventListener('change', () => userSel.value && setScope(userSel.value));
    }
    const card = h('div', { class: 'card corner' },
      h('div', { class: 'card-head' },
        h('div', { class: 'cav', text: (p.name || p.login || '?').charAt(0).toUpperCase() }),
        h('div', {},
          h('h2', { style: 'margin:0', text: SCOPE === 'shared' ? (L ? 'Общие файлы компании' : 'Ընկերության ընդհանուր ֆայլերը')
            : `${p.name || ''}` + (SCOPE.startsWith('u:') ? ` · ${L ? 'уголок пользователя' : 'օգտատիրոջ անկյունը'}` : '') }),
          h('div', { class: 'tiny muted', text: SCOPE === 'shared'
            ? (L ? 'Видят все пользователи. Изменять и удалять может администратор.' : 'Տեսնում են բոլորը: Փոխել և ջնջել կարող է ադմինը:')
            : `${p.login || ''} · ${p.role === 'admin' ? (L ? 'администратор' : 'ադմին') : (L ? 'пользователь' : 'օգտատեր')}`
              + (SCOPE === 'me' ? ` · IP ${c.ip || '—'}` : (p.last_ip ? ` · ${L ? 'последний IP' : 'վերջին IP'} ${p.last_ip}` : ''))
              + (p.last_seen ? ` · ${L ? 'был' : 'եղել է'} ${dt(p.last_seen)}` : '') })),
        h('div', { class: 'right' }, tabs, userSel)));
    if (SCOPE !== 'shared') {
      const grid = h('div', { class: 'catgrid' });
      (c.categories || []).forEach(cat => grid.append(h('button', {
        class: 'cat' + (PATH === cat.path ? ' sel' : ''), onClick: () => { PATH = cat.path; q.value = ''; load(); drawHead(); },
      }, h('span', { class: 'ci', text: CAT_IC[cat.kind] || '📁' }),
        h('span', { class: 'cn', text: L ? (CAT_RU[cat.kind] || cat.name) : cat.name }),
        h('b', { text: nf(cat.files) }))));
      grid.append(h('button', { class: 'cat', dataset: { go: 'quarterly' } },
        h('span', { class: 'ci', text: '📈' }), h('span', { class: 'cn', text: L ? 'Квартальные отчёты' : 'Հաշվետվություններ (սլայդ)' }),
        h('b', { text: nf(c.decks || 0) })));
      card.append(grid);
      if (c.recent?.length && !PATH) {
        card.append(h('h3', { style: 'margin:14px 0 8px', text: L ? 'Последние' : 'Վերջինները' }),
          h('div', { class: 'list' }, ...c.recent.slice(0, 6).map(it => h('div', { class: 'li', style: 'cursor:pointer',
            onClick: () => open(it, L) },
          h('span', { style: 'font-size:18px', text: fileIcon(it.ext) }),
          h('div', { class: 't' }, h('b', { text: it.name }), h('div', { class: 's', text: `${it.path.split('/').slice(0, -1).join(' / ') || '—'} · ${dt(it.modified)}` })),
          EDITABLE.includes(it.ext) ? h('button', { class: 'btn sm', title: t('sec.editor'), onClick: e => { e.stopPropagation(); editIt(it); } }, '✏️') : null,
          h('a', { class: 'btn sm', href: fileUrl(it) + '&download=1', onClick: e => e.stopPropagation() }, '⬇️')))));
      }
    }
    head.append(card);
  }
  function setScope(s) { SCOPE = s; PATH = ''; q.value = ''; drawHead(); load(); }

  const upInput = h('input', { type: 'file', multiple: true, style: 'display:none' });
  upInput.addEventListener('change', () => upInput.files.length && upload(upInput.files));
  const bar = h('div', { class: 'card' },
    h('div', { class: 'card-head' },
      h('h2', { style: 'margin:0', text: '🗂 ' + (L ? 'Файлы и папки' : 'Ֆայլեր և թղթապանակներ') }),
      h('div', { class: 'right' }, statsBox,
        h('button', { class: 'btn', onClick: () => mkdir() }, '📁 ' + (L ? 'Папка' : 'Թղթապանակ')),
        h('button', { class: 'btn primary', onClick: () => upInput.click() }, '⬆️ ' + t('btn.upload')), upInput)),
    h('div', { class: 'search', style: 'margin-bottom:10px' }, q), crumbs, h('div', { class: 'hr' }), items);
  bar.addEventListener('dragover', e => { e.preventDefault(); bar.classList.add('over'); });
  bar.addEventListener('dragleave', () => bar.classList.remove('over'));
  bar.addEventListener('drop', e => { e.preventDefault(); bar.classList.remove('over');
    if (e.dataTransfer.files.length) upload(e.dataTransfer.files); });
  root.append(head, bar);

  async function upload(files) {
    const fd = new FormData();
    fd.append('path', PATH);
    fd.append('scope', SCOPE);
    [...files].forEach(f => fd.append('files', f));
    loader(true, L ? 'Загружаю…' : 'Բեռնում եմ…');
    try {
      const r = await api('/api/vault/upload', { method: 'POST', form: fd });
      toast(`✅ ${r.items.length} ${t('word.files').toLowerCase()}`);
      load(); drawHead();
    } catch (e) { /* toast */ } finally { loader(false); upInput.value = ''; }
  }
  async function mkdir() {
    const name = await promptDlg(L ? 'Название папки' : 'Թղթապանակի անունը');
    if (!name) return;
    await api('/api/vault/mkdir', { method: 'POST', body: { path: PATH, name, scope: SCOPE } });
    toast(t('msg.saved')); load();
  }
  async function load() {
    const needle = q.value.trim();
    clear(crumbs); clear(items);
    api(`/api/vault/stats?${qs()}`, { quiet: true })
      .then(st => { statsBox.textContent = `${nf(st.files)} ${L ? 'файлов' : 'ֆայլ'} · ${bytes(st.size)}`; })
      .catch(() => {});
    if (needle.length >= 2) {
      crumbs.append(h('span', { class: 'badge plain', text: `🔍 ${needle}` }),
        h('button', { onClick: () => { q.value = ''; load(); } }, '✕ ' + t('btn.close')));
      const rows = await api(`/api/vault/search?q=${encodeURIComponent(needle)}&${qs()}`);
      if (!rows.length) { items.append(emptyBox(L ? 'Ничего не найдено' : 'Ոչինչ չգտնվեց', '🔍')); return; }
      items.append(grid(rows, true));
      return;
    }
    let data;
    try { data = await api(`/api/vault/list?path=${encodeURIComponent(PATH)}&${qs()}`); } catch (e) {
      if (PATH) { PATH = ''; return load(); }
      return;
    }
    crumbs.append(h('button', { onClick: () => { PATH = ''; load(); drawHead(); } },
      (SCOPE === 'shared' ? '🗂 ' : '👤 ') + (SCOPE === 'shared' ? (L ? 'Общие' : 'Ընդհանուր') : t('sec.vault'))));
    data.breadcrumbs.forEach(b => {
      crumbs.append(h('span', { class: 'muted', text: '/' }),
        h('button', { onClick: () => { PATH = b.path; load(); } }, b.name));
    });
    if (!data.items.length) items.append(emptyBox(L ? 'Папка пуста — перетащите файлы сюда'
      : 'Թղթապանակը դատարկ է՝ քաշեք ֆայլերը այստեղ', '📂'));
    else items.append(grid(data.items, false));
  }
  function grid(rows, showPath) {
    const g = h('div', { class: 'vgrid' });
    rows.forEach(it => {
      const card = h('div', { class: 'vitem' });
      card.append(h('button', { class: 'btn sm ghost vmenu', onClick: e => { e.stopPropagation(); menu(it); } }, '⋯'));
      if (it.kind === 'image') card.append(h('img', { class: 'thumb', loading: 'lazy', decoding: 'async', src: fileUrl(it) }));
      else card.append(h('div', { class: 'vi', text: it.is_dir ? '📁' : fileIcon(it.ext) }));
      card.append(h('div', { class: 'vn', text: it.name }),
        h('div', { class: 'vs', text: it.is_dir ? `${it.items ?? 0} ${L ? 'эл.' : 'տարր'}`
          : `${bytes(it.size)} · ${dt(it.modified).slice(0, 10)}` }));
      if (showPath) card.append(h('div', { class: 'tiny muted', text: it.path }));
      card.addEventListener('click', () => {
        if (it.is_dir) { PATH = it.path; q.value = ''; load(); }
        else open(it, L);
      });
      g.append(card);
    });
    return g;
  }
  function editIt(it) {
    location.hash = `#/editor?path=${encodeURIComponent(it.path)}&scope=${encodeURIComponent(SCOPE)}`;
  }
  function open(it) {
    const url = fileUrl(it);
    if (it.kind === 'image') {
      modal({ title: it.name, wide: true, body: h('img', { src: url, style: 'width:100%;border-radius:10px' }),
        actions: [{ label: '⬇️ ' + t('btn.download'), onClick: () => { window.location.href = url + '&download=1'; } }] });
      return;
    }
    if (it.ext === 'pdf') { window.open(url, '_blank'); return; }
    if (it.kind === 'audio') {
      modal({ title: it.name, body: h('audio', { controls: true, src: url, style: 'width:100%' }) });
      return;
    }
    if (it.ext === 'docx') { window.open(`/api/vault/print?path=${encodeURIComponent(it.path)}&${qs()}`, '_blank'); return; }
    if (EDITABLE.includes(it.ext)) { editIt(it); return; }
    window.location.href = url + '&download=1';
  }
  function menu(it) {
    const url = fileUrl(it);
    const ro = SCOPE === 'shared' && S.user?.role !== 'admin';
    const row = (icon, label, fn) => h('button', { class: 'btn block', style: 'justify-content:flex-start;margin-bottom:6px',
      onClick: async () => { m.close(); await fn(); } }, `${icon}  ${label}`);
    const m = modal({ title: it.name, body: h('div', {},
      !it.is_dir ? row('👁', t('btn.open'), () => open(it)) : null,
      !it.is_dir && EDITABLE.includes(it.ext) ? row('✏️', L ? 'Изменить (редактор)' : 'Խմբագրել', () => editIt(it)) : null,
      !it.is_dir ? row('🖨', t('btn.print'), () => {
        if (it.ext === 'pdf') window.open(url, '_blank');
        else if (it.ext === 'docx') window.open(`/api/vault/print?path=${encodeURIComponent(it.path)}&${qs()}&auto=1`, '_blank');
        else toast(L ? 'Этот формат печатается только после скачивания' : 'Այս ձևաչափը տպվում է ներբեռնելուց հետո', 'warn');
      }) : null,
      !it.is_dir ? row('⬇️', t('btn.download'), () => { window.location.href = url + '&download=1'; }) : null,
      !it.is_dir && SCOPE !== 'me' ? row('📥', L ? 'Копию в мой уголок' : 'Պատճեն իմ անկյունում', async () => {
        await api('/api/vault/copy', { method: 'POST', body: { path: it.path, scope: SCOPE } });
        toast(t('msg.saved'));
      }) : null,
      ro ? null : row('✏️', L ? 'Переименовать' : 'Վերանվանել', async () => {
        const name = await promptDlg(L ? 'Новое имя' : 'Նոր անունը', { value: it.name });
        if (!name) return;
        await api('/api/vault/rename', { method: 'POST', body: { path: it.path, name, scope: SCOPE } });
        toast(t('msg.saved')); load();
      }),
      ro ? null : row('📂', L ? 'Переместить' : 'Տեղափոխել', () => moveDlg(it)),
      ro ? null : row('🗑', t('btn.delete'), async () => {
        if (!await confirmDlg(L ? `Удалить «${it.name}»?` : `Ջնջե՞լ «${it.name}»-ը:`)) return;
        await api(`/api/vault/item?path=${encodeURIComponent(it.path)}&${qs()}`, { method: 'DELETE' });
        toast(t('msg.deleted')); load(); drawHead();
      })) });
  }
  async function moveDlg(it) {
    const tree = await api(`/api/vault/tree?${qs()}`);
    const list = h('div', { class: 'list scroll' });
    const doMove = async to => {
      await api('/api/vault/move', { method: 'POST', body: { path: it.path, to, scope: SCOPE } });
      toast(t('msg.saved')); m.close(); load();
    };
    const addRow = (node, depth) => {
      list.append(h('button', { class: 'li', style: `cursor:pointer;border:0;width:100%;text-align:left;padding-left:${12 + depth * 18}px`,
        onClick: () => doMove(node.path) }, `📁 ${node.name}`));
      (node.children || []).forEach(c => addRow(c, depth + 1));
    };
    list.append(h('button', { class: 'li', style: 'cursor:pointer;border:0;width:100%;text-align:left',
      onClick: () => doMove('') }, '🏠 ' + (L ? 'Корень' : 'Արմատ')));
    tree.forEach(n => addRow(n, 0));
    const m = modal({ title: `📂 ${L ? 'Куда переместить' : 'Ուր տեղափոխել'}`, body: list });
  }
  q.addEventListener('input', debounce(load, 280));
  await Promise.all([drawHead(), load()]);
  return root;
}
