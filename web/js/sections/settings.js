// ⚙️ Կարգավորումներ՝ ցանցեր և հասցեներ, հաճախորդներ, MP3 թղթապանակ, լեզու/թեմա, համակարգ
import { S, api, clear, confirmDlg, debounce, dt, emptyBox, field, h, highlight, loader, modal, nf,
  photoButton, promptDlg, setLang, setTheme, t, toast } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Сети, адреса, клиенты, MP3'
  : 'Ցանցեր, հասցեներ, հաճախորդներ, MP3';

export async function render() {
  const L = S.lang === 'ru' ? 1 : 0;
  const root = h('div');
  const [nets, clients, folder, diag] = await Promise.all([
    api('/api/networks'), api('/api/clients'),
    api('/api/drive/folder', { quiet: true }).catch(() => ({ folder: '' })),
    api('/api/diagnostics', { quiet: true }).catch(() => null),
  ]);

  // ------------------------------------------------ ցանցեր և հասցեներ
  const netsBox = h('div');
  const q = h('input', { type: 'search', placeholder: L ? 'Поиск адреса…' : 'Որոնել հասցե…' });
  const drawNets = async (data) => {
    const rows = data || await api('/api/networks');
    clear(netsBox);
    const needle = q.value.trim().toLowerCase();
    rows.forEach(n => {
      const matches = needle ? n.addresses.map((a, i) => [a, i]).filter(([a]) => a.toLowerCase().includes(needle)) : [];
      if (needle && !matches.length && !n.name.toLowerCase().includes(needle)) return;
      const list = h('div', { class: 'list', style: 'margin-bottom:10px' });
      const addBtn = h('button', { class: 'btn sm' }, '➕ ' + (L ? 'Адреса' : 'Հասցեներ'));
      addBtn.addEventListener('click', async () => {
        const txt = await promptDlg(L ? 'Адреса (каждый с новой строки)' : 'Հասցեներ (յուրաքանչյուրը նոր տողից)',
          { textarea: true, title: n.name });
        if (!txt) return;
        const r = await api(`/api/networks/${n.index}/addresses`, { method: 'POST', body: { text: txt } });
        toast(`${t('btn.add')}: ${r.added}` + (r.skipped ? ` · ${L ? 'повторы' : 'կրկնվող'}: ${r.skipped}` : ''));
        S.meta.addresses_total += r.added;
        drawNets();
      });
      // 📷 հասցեների ցուցակի նկար/ֆայլ -> ստուգում -> ավելացում
      const photoAdd = photoButton({ section: `Address list for shop network «${n.name}»`, cls: 'btn sm', label: '📷',
        title: L ? 'Адреса с фото / файла' : 'Հասցեներ նկարից / ֆայլից',
        fields: [{ key: 'addresses', type: 'list', label: 'All shop addresses in the document, one per item',
          hint: 'keep street, house number, city/district and floor as written' }],
        onResult: async res => {
          const found = res.values?.addresses || [];
          if (!found.length) return;
          const txt = await promptDlg(L ? 'Проверьте адреса (каждый с новой строки)' : 'Ստուգեք հասցեները (յուրաքանչյուրը նոր տողից)',
            { textarea: true, title: n.name, value: found.join('\n') });
          if (!txt) return;
          const r = await api(`/api/networks/${n.index}/addresses`, { method: 'POST', body: { text: txt } });
          toast(`${t('btn.add')}: ${r.added}` + (r.skipped ? ` · ${L ? 'повторы' : 'կրկնվող'}: ${r.skipped}` : ''));
          S.meta.addresses_total += r.added;
          drawNets();
        } });
      list.append(h('div', { class: 'li', style: 'background:var(--card-2)' },
        h('div', { class: 't' }, h('b', { text: n.name }),
          h('div', { class: 's', text: `${n.addresses.length} ${L ? 'адресов' : 'հասցե'}` })),
        photoAdd, addBtn,
        h('button', { class: 'btn sm ghost', onClick: () => window.open(`/print/addresses?nets=${n.index}`, '_blank') }, '🖨')));
      (needle ? matches : n.addresses.map((a, i) => [a, i])).slice(0, needle ? 50 : 500).forEach(([a, ai]) => {
        list.append(h('div', { class: 'li' },
          h('div', { class: 't' }, h('span', { html: highlight(a, needle) })),
          h('button', { class: 'btn sm ghost danger', onClick: async () => {
            if (!await confirmDlg(L ? `Удалить адрес «${a}»?` : `Ջնջե՞լ «${a}» հասցեն:`)) return;
            await api(`/api/networks/${n.index}/addresses/${ai}`, { method: 'DELETE' });
            S.meta.addresses_total = Math.max(0, S.meta.addresses_total - 1);
            toast(t('msg.deleted')); drawNets();
          } }, '🗑')));
      });
      netsBox.append(list);
    });
    if (!netsBox.children.length) netsBox.append(emptyBox(L ? 'Ничего не найдено' : 'Ոչինչ չգտնվեց', '🔍'));
  };
  q.addEventListener('input', debounce(() => drawNets(), 250));
  const addNet = h('button', { class: 'btn primary' }, '➕ ' + (L ? 'Новая сеть' : 'Նոր ցանց'));
  addNet.addEventListener('click', async () => {
    const name = await promptDlg(L ? 'Название сети' : 'Ցանցի անունը');
    if (!name) return;
    try {
      await api('/api/networks', { method: 'POST', body: { name } });
      toast(t('msg.saved'));
      S.meta.networks = (await api('/api/networks')).map(n => ({ name: n.name, count: n.addresses.length }));
      drawNets();
    } catch (e) { /* toast */ }
  });
  root.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' },
      h('h2', { style: 'margin:0', text: '🏪 ' + (L ? 'Сети и адреса' : 'Ցանցեր և հասցեներ') }),
      h('div', { class: 'right' },
        h('span', { class: 'badge plain', text: `${nets.length} · ${nf(S.meta.addresses_total)}` }),
        h('button', { class: 'btn', onClick: () => window.open('/print/addresses', '_blank') }, '🖨 ' + t('btn.print')),
        addNet)),
    h('div', { class: 'search', style: 'margin-bottom:10px' }, q), netsBox));
  await drawNets(nets);

  // ------------------------------------------------ հաճախորդներ
  const clBox = h('div', { class: 'list scroll sm' });
  const drawClients = async (rows) => {
    const list = rows || await api('/api/clients');
    S.meta.clients = list;
    clear(clBox);
    if (!list.length) clBox.append(emptyBox(L ? 'Список пуст' : 'Ցանկը դատարկ է', '👤'));
    list.forEach(c => clBox.append(h('div', { class: 'li' }, h('div', { class: 't' }, h('b', { text: c })),
      h('button', { class: 'btn sm ghost danger', onClick: async () => {
        if (!await confirmDlg(L ? `Удалить «${c}» из списка?` : `Ջնջե՞լ «${c}»-ը ցանկից:`)) return;
        await api(`/api/clients?name=${encodeURIComponent(c)}`, { method: 'DELETE' });
        drawClients();
      } }, '🗑'))));
  };
  const addCl = h('button', { class: 'btn sm' }, '➕ ' + t('btn.add'));
  addCl.addEventListener('click', async () => {
    const name = await promptDlg(L ? 'Имя клиента' : 'Հաճախորդի անունը');
    if (!name) return;
    await api('/api/clients', { method: 'POST', body: { name } });
    drawClients();
  });

  // ------------------------------------------------ Drive + ընդհանուր
  const mp3Folder = h('input', { type: 'text', value: folder.folder || '', placeholder: 'https://drive.google.com/drive/folders/…' });
  const saveDrive = h('button', { class: 'btn primary' }, '💾 ' + t('btn.save'));
  saveDrive.addEventListener('click', async () => {
    loader(true);
    try {
      if (mp3Folder.value.trim()) await api('/api/drive/folder', { method: 'POST', body: { link: mp3Folder.value } });
      S.meta.settings = await api('/api/settings');
      toast(t('msg.saved'));
    } catch (e) { /* toast */ } finally { loader(false); }
  });

  const langSeg = h('div', { class: 'seg' },
    h('button', { class: S.lang === 'hy' ? 'on' : '', onClick: () => setLang('hy') }, 'ՀԱՅԵՐԵՆ'),
    h('button', { class: S.lang === 'ru' ? 'on' : '', onClick: () => setLang('ru') }, 'РУССКИЙ'));
  const themeSeg = h('div', { class: 'seg' },
    h('button', { class: S.theme === 'light' ? 'on' : '', onClick: () => setTheme('light') }, '☀️ ' + (L ? 'Светлая' : 'Լուսավոր')),
    h('button', { class: S.theme === 'dark' ? 'on' : '', onClick: () => setTheme('dark') }, '🌙 ' + (L ? 'Тёмная' : 'Մուգ')));

  root.append(h('div', { class: 'grid c2' },
    h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h3', { style: 'margin:0', text: '👤 ' + (L ? 'Клиенты' : 'Հաճախորդներ') }),
        h('div', { class: 'right' }, addCl)), clBox),
    h('div', { class: 'card' },
      h('h3', { text: '☁️ Google Drive · MP3' }),
      h('p', { class: 'small muted', text: L ? 'Тех. мониторинг и АКТ больше не используют Google Drive — данные хранятся в приложении (раздел «Тех. мониторинг»).'
        : 'Տեխ. մոնիտորինգը և ԱԿՏ-ը այլևս Google Drive չեն օգտագործում՝ տվյալները պահվում են հավելվածում («Տեխ. մոնիտորինգ» բաժին):' }),
      field(L ? 'Папка с MP3 роликами' : 'MP3 հոլովակների թղթապանակ', mp3Folder,
        { hint: L ? 'Доступ: «Anyone with the link — Viewer»' : 'Հասանելիություն՝ «Anyone with the link — Viewer»' }),
      h('div', { class: 'row' }, saveDrive))));
  await drawClients(clients);

  // ------------------------------------------------ հղում գործընկերների համար
  const net = await api('/api/network', { quiet: true }).catch(() => null);
  if (net) {
    const copy = async url => {
      try { await navigator.clipboard.writeText(url); toast(L ? 'Ссылка скопирована' : 'Հղումը պատճենվեց'); }
      catch (e) { window.prompt(L ? 'Скопируйте ссылку:' : 'Պատճենեք հղումը՝', url); }
    };
    const rows = net.urls.map(u => h('div', { class: 'li' },
      h('div', { class: 't' }, h('b', { text: u })),
      h('button', { class: 'btn sm', onClick: () => copy(u) }, '📋 ' + (L ? 'Копировать' : 'Պատճենել'))));
    root.append(h('div', { class: 'card' },
      h('h3', { text: '🔗 ' + (L ? 'Ссылка для коллег' : 'Հղում գործընկերների համար') }),
      net.shared && rows.length
        ? h('div', {}, h('div', { class: 'list' }, ...rows),
          h('p', { class: 'small muted', text: L
            ? 'Коллеги должны быть в той же сети (Wi-Fi / офис). Адрес 127.0.0.1 открывается только на этом компьютере. Компьютер и run.bat должны быть включены.'
            : 'Գործընկերները պետք է լինեն նույն ցանցում (Wi-Fi / գրասենյակ): 127.0.0.1 հասցեն բացվում է միայն այս համակարգչում: Համակարգիչը և run.bat-ը պետք է միացված լինեն:' }),
          h('p', { class: 'small', text: '🔐 ' + (L
            ? 'Каждый входит под своим логином. Новый человек нажимает «Запросить доступ», а администратор подтверждает в окне сервера: allow <логин>.'
            : 'Յուրաքանչյուրը մտնում է իր լոգինով: Նոր մարդը սեղմում է «Հարցում», ադմինը հաստատում է սերվերի պատուհանում՝ allow <լոգին>:') }))
        : h('p', { class: 'small muted', text: L
          ? 'Сервер сейчас доступен только на этом компьютере. В run.bat поставьте APP_HOST=0.0.0.0 и перезапустите.'
          : 'Սերվերը հիմա հասանելի է միայն այս համակարգչում: run.bat-ում դրեք APP_HOST=0.0.0.0 և վերագործարկեք:' })));
  }

  root.append(myPasswordCard(L));
  if (S.user?.role === 'admin') root.append(await adminCards(L));

  root.append(h('div', { class: 'grid c2' },
    h('div', { class: 'card' }, h('h3', { text: '🎨 ' + (L ? 'Внешний вид' : 'Տեսք') }),
      field(L ? 'Язык интерфейса' : 'Ծրագրի լեզուն', langSeg),
      field(L ? 'Тема' : 'Թեմա', themeSeg)),
    h('div', { class: 'card' }, h('h3', { text: 'ℹ️ ' + (L ? 'О приложении' : 'Հավելվածի մասին') }),
      h('div', { class: 'list' },
        info(L ? 'Компания' : 'Ընկերություն', S.meta.company?.name),
        info(L ? 'Адрес' : 'Հասցե', S.meta.company?.address),
        info(L ? 'Телефон' : 'Հեռախոս', S.meta.company?.phone),
        info('Email', S.meta.company?.email),
        info(L ? 'PDF-конвертер' : 'PDF փոխարկիչ', S.meta.pdf?.how),
        info('Python', diag?.system?.python || '—'),
        info(L ? 'Папка' : 'Թղթապանակ', diag?.system?.base || '—')),
      h('div', { class: 'row', style: 'margin-top:10px' },
        h('button', { class: 'btn', onClick: () => document.getElementById('fixik-btn').click() },
          '🛠 ' + (L ? 'Проверка системы' : 'Համակարգի ստուգում'))))));
  return root;
}

const info = (k, v) => h('div', { class: 'li' }, h('div', { class: 't' }, h('b', { text: k })),
  h('div', { class: 'small muted', style: 'text-align:right;word-break:break-all', text: String(v || '—') }));

/* ---------------------------------------------------------------- 🔑 իմ գաղտնաբառը (բոլորի համար) */
function myPasswordCard(L) {
  const old = h('input', { type: 'password', autocomplete: 'current-password', placeholder: L ? 'Текущий пароль' : 'Ընթացիկ գաղտնաբառ' });
  const nw = h('input', { type: 'password', autocomplete: 'new-password', placeholder: L ? 'Новый пароль (мин. 8)' : 'Նոր գաղտնաբառ (առնվազն 8)' });
  const nw2 = h('input', { type: 'password', autocomplete: 'new-password', placeholder: L ? 'Повторите новый' : 'Կրկնեք նորը' });
  const save = h('button', { class: 'btn primary' }, '💾 ' + (L ? 'Сменить пароль' : 'Փոխել գաղտնաբառը'));
  save.addEventListener('click', async () => {
    if (nw.value !== nw2.value) { toast(L ? 'Новые пароли не совпадают' : 'Նոր գաղտնաբառերը չեն համընկնում', 'err'); return; }
    try {
      await api('/api/me/password', { method: 'POST', body: { old: old.value, new: nw.value } });
      old.value = nw.value = nw2.value = '';
      toast(L ? 'Пароль изменён' : 'Գաղտնաբառը փոխված է', 'ok');
    } catch (e) { /* toast */ }
  });
  return h('div', { class: 'card' },
    h('h3', { text: `🔑 ${L ? 'Мой вход' : 'Իմ մուտքը'} · ${S.user?.login || ''}` }),
    h('div', { class: 'grid c3' }, old, nw, nw2),
    h('div', { class: 'row', style: 'margin-top:10px' }, save,
      h('span', { class: 'tiny muted', text: L ? 'Никому не сообщайте пароль. Забыли — попросите администратора.'
        : 'Գաղտնաբառը ոչ մեկին մի ասեք: Մոռացե՞լ եք՝ դիմեք ադմինին:' })));
}

/* ---------------------------------------------------------------- ադմին՝ օգտատերեր, անվտանգություն, ճանաչում */
async function adminCards(L) {
  const box = h('div');
  box.append(await usersCard(L));
  const grid = h('div', { class: 'grid c2' });
  grid.append(await recognitionCard(L));
  box.append(await securityCard(L), grid);
  return box;
}

const STATUS = L => ({ active: ['ok', L ? 'доступ есть' : 'մուտք կա'], pending: ['warn', L ? 'ждёт' : 'սպասում է'],
  blocked: ['err', L ? 'заблокирован' : 'արգելափակված'] });

async function usersCard(L) {
  const card = h('div', { class: 'card' });
  const draw = async (rows) => {
    let d;
    try { d = rows ? { users: rows, online: [] } : await api('/api/admin/users', { quiet: true }); }
    catch (e) { clear(card).append(h('p', { class: 'small', text: e.message })); return; }
    clear(card);
    const addBtn = h('button', { class: 'btn primary' }, '➕ ' + (L ? 'Новый пользователь' : 'Նոր օգտատեր'));
    addBtn.addEventListener('click', () => createUserDlg(L, draw));
    const pending = d.users.filter(u => u.status === 'pending').length;
    card.append(h('div', { class: 'card-head' },
      h('h2', { style: 'margin:0', text: `👥 ${L ? 'Пользователи' : 'Օգտատերեր'} · ${d.users.length}` }),
      h('div', { class: 'right' },
        pending ? h('span', { class: 'badge warn', text: `⏳ ${L ? 'ждут' : 'սպասում են'}: ${pending}` }) : null,
        h('button', { class: 'btn sm', onClick: () => draw() }, '🔄'), addBtn)),
    h('p', { class: 'tiny muted', text: L
      ? 'Каждый входит по своему логину и паролю (ссылка та же, например http://192.168.10.131:8000). Создайте вход здесь или подтвердите запрос человека.'
      : 'Յուրաքանչյուրը մտնում է իր լոգինով և գաղտնաբառով (հղումը նույնն է): Ստեղծեք մուտքը այստեղ կամ հաստատեք մարդու հարցումը:' }));
    const tb = h('tbody');
    d.users.forEach(u => {
      const [cls, txt] = STATUS(L)[u.status] || ['', u.status];
      const act = (label, action, opts = {}) => h('button', { class: `btn sm ${opts.cls || 'ghost'}`, title: opts.title || '',
        onClick: () => userAction(u, action, L, draw, opts) }, label);
      tb.append(h('tr', {},
        h('td', {}, h('span', { class: 'badge ' + (u.online ? 'ok' : 'plain'), text: u.online ? '●' : '○' })),
        h('td', {}, h('b', { text: u.name }), h('div', { class: 'tiny muted', text: u.login + (u.role === 'admin' ? ' · admin' : '') })),
        h('td', {}, h('span', { class: 'badge ' + cls, text: txt })),
        h('td', { class: 'small' }, h('a', { href: '#', onClick: e => { e.preventDefault(); ipsDlg(u.login, L); }, text: u.last_ip || '—' }),
          h('div', { class: 'tiny muted', text: u.last_seen ? dt(u.last_seen) : '—' })),
        h('td', {}, h('div', { class: 'row tight', style: 'justify-content:flex-end;flex-wrap:wrap' },
          u.status !== 'active' ? act('✅', 'allow', { cls: 'primary', title: L ? 'Дать доступ' : 'Թույլատրել' }) : null,
          u.status === 'active' && u.login !== S.user?.login ? act('⛔', 'block', { title: L ? 'Заблокировать' : 'Արգելափակել' }) : null,
          act('🔑', 'passwd', { title: L ? 'Новый пароль' : 'Նոր գաղտնաբառ' }),
          act('✏️', 'name', { title: L ? 'Имя' : 'Անուն' }),
          u.login !== S.user?.login ? act(u.role === 'admin' ? '👤' : '⭐', 'role', { title: u.role === 'admin' ? (L ? 'Сделать обычным' : 'Դարձնել սովորական') : (L ? 'Сделать админом' : 'Դարձնել ադմին') }) : null,
          act('📦', 'merge', { title: L ? 'Передать файлы другому' : 'Փոխանցել ֆայլերը' }),
          u.login !== S.user?.login ? act('🗑', 'delete', { cls: 'ghost danger', title: t('btn.delete') }) : null))));
    });
    card.append(h('div', { class: 'tablewrap' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ...['', L ? 'Пользователь' : 'Օգտատեր', L ? 'Статус' : 'Կարգավիճակ', 'IP', ''].map(x => h('th', { text: x })))), tb)));
    if (d.users.some(u => u.login.startsWith('guest-'))) card.append(h('p', { class: 'tiny', style: 'color:var(--warn)', text: L
      ? '⚠️ guest-… — старые автоматические входы без пароля. Они отключены ради безопасности, файлы сохранены: кнопкой 📦 передайте их настоящему пользователю, потом удалите guest.'
      : '⚠️ guest-…՝ հին ավտոմատ մուտքեր առանց գաղտնաբառի: Անջատված են անվտանգության համար, ֆայլերը պահված են՝ 📦 կոճակով փոխանցեք իսկական օգտատիրոջը, հետո ջնջեք guest-ը:' }));
  };
  await draw();
  return card;
}

function createUserDlg(L, done) {
  const name = h('input', { type: 'text', placeholder: L ? 'Имя Фамилия' : 'Անուն Ազգանուն' });
  const login = h('input', { type: 'text', placeholder: 'ivan', autocomplete: 'off' });
  const pass = h('input', { type: 'text', autocomplete: 'off', value: genPass() });
  const admin = h('input', { type: 'checkbox' });
  modal({ title: '➕ ' + (L ? 'Новый пользователь' : 'Նոր օգտատեր'), body: h('div', {},
    field(L ? 'Имя' : 'Անուն', name),
    field(L ? 'Логин (латиница, цифры)' : 'Լոգին (լատինատառ, թվեր)', login),
    field(L ? 'Пароль (мин. 8) — передайте человеку' : 'Գաղտնաբառ (առնվազն 8)՝ փոխանցեք մարդուն', pass,
      { hint: L ? 'Человек сможет сменить его сам: ⚙️ Настройки → 🔑 Мой вход' : 'Մարդը կարող է ինքը փոխել՝ ⚙️ → 🔑 Իմ մուտքը' }),
    h('label', { class: 'row tight small' }, admin, L ? 'Администратор (видит всё, управляет пользователями)' : 'Ադմին (տեսնում է ամեն ինչ)')),
  actions: [{ label: t('btn.cancel') }, { label: '✅ ' + t('btn.save'), primary: true, onClick: async () => {
    try {
      const r = await api('/api/admin/users', { method: 'POST', body: { name: name.value, login: login.value.trim().toLowerCase(),
        password: pass.value, role: admin.checked ? 'admin' : 'user' } });
      const msg = `${L ? 'Ссылка' : 'Հղում'}: ${location.origin}\n${L ? 'Логин' : 'Լոգին'}: ${r.login}\n${L ? 'Пароль' : 'Գաղտնաբառ'}: ${pass.value}`;
      try { await navigator.clipboard.writeText(msg); } catch (e) { /* http-ում clipboard-ը կարող է չաշխատել */ }
      modal({ title: '✅ ' + (L ? 'Вход создан' : 'Մուտքը ստեղծված է'), body: h('div', {},
        h('p', { class: 'small', text: L ? 'Отправьте человеку (уже скопировано, если браузер разрешил):' : 'Ուղարկեք մարդուն՝' }),
        h('pre', { style: 'white-space:pre-wrap;background:var(--card-2);padding:10px;border-radius:8px', text: msg })) });
      done(r.users);
    } catch (e) { return false; }
  } }] });
}

function genPass() {
  const abc = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789';
  const a = new Uint32Array(10);
  crypto.getRandomValues(a);
  return [...a].map(x => abc[x % abc.length]).join('');
}

async function userAction(u, action, L, done) {
  let body = {};
  if (action === 'passwd') {
    const pw = await promptDlg(L ? `Новый пароль для ${u.login} (мин. 8)` : `Նոր գաղտնաբառ ${u.login}-ի համար (առնվազն 8)`, { value: genPass() });
    if (!pw) return;
    body = { password: pw };
  } else if (action === 'name') {
    const nm = await promptDlg(L ? 'Имя Фамилия' : 'Անուն Ազգանուն', { value: u.name });
    if (!nm) return;
    body = { name: nm };
  } else if (action === 'role') {
    body = { role: u.role === 'admin' ? 'user' : 'admin' };
  } else if (action === 'merge') {
    const to = await promptDlg(L ? `Передать все файлы «${u.login}» пользователю (логин):` : `Փոխանցել «${u.login}»-ի բոլոր ֆայլերը օգտատիրոջը (լոգին)՝`);
    if (!to) return;
    body = { to: to.trim().toLowerCase() };
  } else if (action === 'delete' || action === 'block') {
    const q = action === 'delete' ? (L ? `Удалить пользователя ${u.login}? Его файлы останутся на диске.` : `Ջնջե՞լ ${u.login}-ը: Ֆայլերը կմնան:`)
      : (L ? `Заблокировать ${u.login}? Он сразу выйдет из сайта.` : `Արգելափակե՞լ ${u.login}-ը:`);
    if (!await confirmDlg(q)) return;
  }
  try {
    const r = await api(`/api/admin/users/${encodeURIComponent(u.login)}/${action}`, { method: 'POST', body });
    toast(action === 'merge' ? `${L ? 'Передано файлов' : 'Փոխանցված ֆայլեր'}: ${r.moved}` : t('msg.saved'), 'ok');
    if (action === 'passwd') modal({ title: '🔑 ' + u.login, body: h('pre', { text: `${L ? 'Логин' : 'Լոգին'}: ${u.login}\n${L ? 'Пароль' : 'Գաղտնաբառ'}: ${body.password}` }) });
    done(r.users);
  } catch (e) { /* toast */ }
}

/* ---------------------------------------------------------------- 🛡 անվտանգություն */
const SEC_KIND = {
  scanner: ['🕷', 'Сканер уязвимостей', 'Խոցելիության սկաներ'], ban: ['⛔', 'IP заблокирован', 'IP արգելափակված'],
  unban: ['✅', 'IP разблокирован', 'IP-ն բացված է'], flood: ['🌊', 'Слишком много запросов', 'Չափից շատ հարցումներ'],
  csrf: ['🎭', 'Запрос с чужого сайта (CSRF)', 'Հարցում օտար կայքից (CSRF)'], 'bad-host': ['🌐', 'Чужой домен', 'Օտար դոմեն'],
  'too-big': ['📦', 'Слишком большой файл', 'Չափազանց մեծ ֆայլ'], settings: ['⚙️', 'Настройки изменены', 'Կարգավորումները փոխվեցին'],
  'internet-off': ['🔒', 'Вход из интернета закрыт', 'Ինտերնետից մուտքը փակ է'],
};
const USER_EV = { 'login-fail': '❌', 'login-locked': '🔒', login: '🔓', logout: '↩', request: '📨', 'login-blocked': '⛔' };

async function securityCard(L) {
  const card = h('div', { class: 'card' });
  const draw = async (data) => {
    let d;
    try { d = data || await api('/api/admin/security', { quiet: true }); } catch (e) { clear(card).append(h('p', { text: e.message })); return; }
    clear(card);
    const post = async (url, body) => { try { await draw(await api(url, { method: 'POST', body })); toast(t('msg.saved')); } catch (e) { /* toast */ } };
    const sw = (key, label, hint) => {
      const cb = h('input', { type: 'checkbox', checked: !!d.settings[key] });
      cb.addEventListener('change', () => post('/api/admin/security', { [key]: cb.checked }));
      return h('label', { class: 'li', style: 'cursor:pointer' }, cb, h('div', { class: 't' }, h('b', { text: label }), h('div', { class: 's', text: hint })));
    };
    const banIp = h('input', { type: 'text', placeholder: 'IP', style: 'width:150px' });
    const banBtn = h('button', { class: 'btn sm' }, '⛔ ' + (L ? 'Заблокировать' : 'Արգելափակել'));
    banBtn.addEventListener('click', () => banIp.value.trim() && post('/api/admin/security/ban', { ip: banIp.value.trim(), hours: 0, reason: L ? 'вручную' : 'ձեռքով' }));
    const doms = h('input', { type: 'text', value: d.settings.domains || '', placeholder: 'mixmedia.am' });
    const domSave = h('button', { class: 'btn sm' }, '💾');
    domSave.addEventListener('click', () => post('/api/admin/security', { domains: doms.value }));

    const st = d.stats || {};
    card.append(h('div', { class: 'card-head' },
      h('h2', { style: 'margin:0', text: '🛡 ' + (L ? 'Безопасность сайта' : 'Կայքի անվտանգություն') }),
      h('div', { class: 'right' },
        h('span', { class: 'badge ' + (d.bans.length ? 'warn' : 'ok'), text: `⛔ ${d.bans.length}` }),
        h('button', { class: 'btn sm', onClick: () => draw() }, '🔄'))),
      h('div', { class: 'grid c4', style: 'margin-bottom:12px' },
        ...[['🕷', L ? 'Сканеров отбито' : 'Սկաներներ', st.scanner], ['⛔', L ? 'Блокировок' : 'Արգելափակումներ', st.ban],
          ['🎭', 'CSRF', st.csrf], ['🌊', L ? 'Флуд' : 'Ֆլուդ', st.flood]].map(([i, k, v]) =>
          h('div', { class: 'tile' }, h('div', { class: 'k', text: `${i} ${k}` }), h('div', { class: 'v', text: nf(v || 0) })))),
      h('div', { class: 'grid c2' },
        h('div', {},
          h('h3', { text: L ? 'Защита' : 'Պաշտպանություն' }),
          h('div', { class: 'list' },
            sw('autoban', L ? 'Автоблокировка атакующих IP' : 'Հարձակվող IP-ների ավտոարգելափակում',
              L ? 'подбор пароля, сканеры, флуд → блок на 24 ч (из офисной сети — на 1 ч)' : 'գաղտնաբառի ընտրություն, սկաներներ → 24 ժամ (գրասենյակից՝ 1 ժամ)'),
            sw('csrf', L ? 'Защита от чужих сайтов (CSRF)' : 'Պաշտպանություն օտար կայքերից (CSRF)',
              L ? 'изменения принимаются только со страниц этого сайта' : 'փոփոխությունները՝ միայն այս կայքից'),
            sw('internet', L ? 'Разрешить вход из интернета' : 'Թույլատրել մուտքը ինտերնետից',
              L ? 'выключите — сайт откроется только в офисной сети' : 'անջատեք՝ կայքը կբացվի միայն գրասենյակի ցանցում')),
          h('h3', { style: 'margin-top:14px', text: L ? '🌐 Домен сайта' : '🌐 Կայքի դոմեն' }),
          h('div', { class: 'inline' }, doms, domSave),
          h('div', { class: 'hint', text: (L ? 'Когда купите домен — впишите его (например mixmedia.am). Запросы с чужих доменов будут отклонены. Ссылки по IP (192.168…) работают всегда.'
            : 'Դոմեն գնելուց հետո գրեք այստեղ: IP հղումները (192.168…) միշտ աշխատում են:') + (d.env_domain ? ` APP_DOMAIN=${d.env_domain}` : '') })),
        h('div', {},
          h('h3', { text: `⛔ ${L ? 'Заблокированные IP' : 'Արգելափակված IP-ներ'}` }),
          h('div', { class: 'list scroll sm' }, ...(d.bans.length ? d.bans.map(b => h('div', { class: 'li' },
            h('div', { class: 't' }, h('b', { text: b.ip }), h('div', { class: 's', text: `${b.reason} · ${b.until ? (L ? 'до ' : 'մինչև ') + dt(b.until) : (L ? 'навсегда' : 'ընդմիշտ')}` })),
            h('button', { class: 'btn sm', onClick: () => post('/api/admin/security/unban', { ip: b.ip }) }, L ? 'Разблокировать' : 'Բացել')))
            : [emptyBox(L ? 'Никто не заблокирован' : 'Ոչ ոք արգելափակված չէ', '✅')])),
          h('div', { class: 'inline', style: 'margin-top:8px' }, banIp, banBtn),
          d.watch.length ? h('div', { class: 'tiny muted', style: 'margin-top:8px', text: (L ? 'Под наблюдением: ' : 'Հսկողության տակ՝ ')
            + d.watch.map(w => `${w.ip} (${w.score}/${d.ban_score})`).join(', ') }) : null)));

    const ev = h('div', { class: 'list scroll' });
    const rows = [...d.events.map(e => ({ at: e.at, icon: (SEC_KIND[e.kind] || ['•'])[0], text: (SEC_KIND[e.kind] || [0, e.kind, e.kind])[L ? 1 : 2], ip: e.ip, detail: e.detail, lvl: e.level })),
      ...d.users_log.filter(e => USER_EV[e.event]).map(e => ({ at: e.at, icon: USER_EV[e.event], text: `${e.event} ${e.login}`, ip: e.ip, detail: e.detail, lvl: e.event === 'login-fail' ? 'warn' : 'info' }))]
      .sort((a, b) => String(b.at).localeCompare(String(a.at))).slice(0, 150);
    rows.forEach(r => ev.append(h('div', { class: 'li' },
      h('span', { text: r.icon }),
      h('div', { class: 't' }, h('b', { text: r.text }), h('div', { class: 's', text: `${dt(r.at)} · ${r.ip || '—'}${r.detail ? ' · ' + r.detail : ''}` })),
      r.ip && r.lvl !== 'info' ? h('button', { class: 'btn sm ghost', title: L ? 'Заблокировать IP' : 'Արգելափակել IP',
        onClick: async () => { if (await confirmDlg(`${L ? 'Заблокировать' : 'Արգելափակե՞լ'} ${r.ip}?`)) post('/api/admin/security/ban', { ip: r.ip, hours: 0, reason: r.text }); } }, '⛔') : null)));
    if (!rows.length) ev.append(emptyBox(L ? 'Событий нет — всё спокойно' : 'Իրադարձություններ չկան', '🛡'));
    card.append(h('details', { style: 'margin-top:14px' },
      h('summary', { style: 'cursor:pointer;font-weight:700', text: `📜 ${L ? 'Журнал безопасности и входов' : 'Անվտանգության և մուտքերի մատյան'} · ${rows.length}` }), ev));
  };
  await draw();
  return card;
}

/* ---------------------------------------------------------------- 📷 ճանաչում (տեղային) */
async function recognitionCard(L) {
  const card = h('div', { class: 'card' });
  const draw = async (st0) => {
    let st = st0 || S.meta.extract || {};
    try { if (!st0) { st = await api('/api/extract/status', { quiet: true }); S.meta.extract = st; } } catch (e) { /* */ }
    clear(card);
    const o = st.ocr || {}, ai = st.local_ai || {};
    const model = h('input', { type: 'text', value: ai.model || 'gemma3:4b', style: 'width:160px' });
    const en = h('input', { type: 'checkbox', checked: ai.enabled !== false });
    const save = h('button', { class: 'btn sm' }, '💾');
    save.addEventListener('click', async () => {
      try { await draw(await api('/api/extract/local-ai', { method: 'POST', body: { enabled: en.checked, model: model.value } })); toast(t('msg.saved')); }
      catch (e) { /* toast */ }
    });
    card.append(h('h3', { text: '📷 ' + (L ? 'Распознавание фото (локально)' : 'Լուսանկարի ճանաչում (տեղային)') }),
      h('p', { class: 'small', text: L
        ? '🔒 Работает на этом компьютере: без интернета, без облака и без API-ключей. Документы никуда не отправляются.'
        : '🔒 Աշխատում է այս համակարգչում՝ առանց ինտերնետի, ամպի և բանալիների: Փաստաթղթերը ոչ մի տեղ չեն ուղարկվում:' }),
      h('div', { class: 'list' },
        h('div', { class: 'li' }, h('span', { text: o.ready ? '✅' : '⚠️' }), h('div', { class: 't' },
          h('b', { text: 'Tesseract OCR' + (o.languages?.length ? ` · ${o.languages.join('+')}` : '') }),
          h('div', { class: 's', text: o.ready ? (L ? 'читает фото и сканы (армянский, русский, английский)' : 'կարդում է նկարներն ու սկանները')
            : (L ? 'не установлен: запустите install_ocr.bat (один раз). Word/Excel/PDF с текстом читаются и без него.'
              : 'տեղադրված չէ՝ գործարկեք install_ocr.bat (մեկ անգամ)') }))),
        h('div', { class: 'li' }, h('span', { text: ai.ready ? '✅' : 'ℹ️' }), h('div', { class: 't' },
          h('b', { text: L ? 'Локальный ИИ (Ollama) — по желанию' : 'Տեղային ԻԻ (Ollama)՝ ըստ ցանկության' }),
          h('div', { class: 's', text: ai.ready ? `${L ? 'включён' : 'միացված է'} · ${ai.model}`
            : !ai.running ? (L ? 'не запущен — поля заполняются по правилам. Для большей точности: install_local_ai.bat' : 'չի աշխատում՝ դաշտերը լրացվում են կանոններով')
              : !ai.has_model ? `${L ? 'нет модели' : 'մոդել չկա'} ${ai.model}: ollama pull ${ai.model}` : (L ? 'выключен' : 'անջատված է') })))),
      h('div', { class: 'row', style: 'margin-top:10px' },
        h('label', { class: 'row tight small' }, en, L ? 'Использовать ИИ' : 'Օգտագործել ԻԻ'), model, save));
  };
  await draw();
  return card;
}

async function ipsDlg(login, L) {
  let d;
  try { d = await api(`/api/admin/users/${encodeURIComponent(login)}/ips`); } catch (e) { return; }
  modal({ title: `🌐 IP · ${d.login}`, wide: true, body: d.ips.length
    ? h('div', { class: 'tablewrap' }, h('table', { class: 'table' },
      h('thead', {}, h('tr', {}, ...['IP', L ? 'Первый раз' : 'Առաջին անգամ', L ? 'Последний раз' : 'Վերջին անգամ',
        L ? 'Раз' : 'Անգամ', L ? 'Браузер' : 'Բրաուզեր'].map(x => h('th', { text: x })))),
      h('tbody', {}, ...d.ips.map(r => h('tr', {}, h('td', { text: r.ip }), h('td', { text: dt(r.first) }),
        h('td', { text: dt(r.last) }), h('td', { text: String(r.count || 0) }),
        h('td', { class: 'tiny muted', text: (r.ua || '').slice(0, 90) }))))))
    : emptyBox(L ? 'IP пока нет' : 'IP դեռ չկա', '🌐') });
}
