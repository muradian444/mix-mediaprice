// 💰 Գնացուցակ (Խանութներ → Գներ)՝ ինչպես mix-media.am/price կայքում.
// Որտեղ գովազդել → Հեռարձակման ծառայություն (փաթեթներ) → Կանխատեսվող արդյունքներ (հաշվիչ + PDF / Telegram / WhatsApp)
import { api, clear, copyText, debounce, field, filesResult, h, loader, modal, nf, t, toast } from '../core.js';

const PERIOD_MONTHS = { month: 1, half: 6, year: 12 };
// էջից էջ անցնելիս ընտրությունները չեն կորչում
const P = { group: '', mode: 'month', period: 'month', pkg: '', sel: new Set(), studio: new Set(), brand: '', contact: '',
  q: '', spots: new Map() };
const PKG_FIELD = { month: 'price', half: 'half', year: 'year' };

// նույնը, ինչ pricecalc.unit_price
export function unitPrice(cfg, pkg, period, month) {
  const own = pkg ? Number(pkg[PKG_FIELD[period]]) || 0 : 0;
  return own || Math.round((month || 0) * (100 - (cfg.discounts[period] || 0)) / 100);
}

const T = (L, hy, ru) => (L ? ru : hy);
const money = v => `${nf(Math.round(v || 0))} ֏`;
const key = (net, i) => `${net}:${i}`;

export function priceSite(pl, L) {
  const cfg = pl.config;
  const G = pl.groups;
  if (!P.group || !G[P.group]?.count) P.group = ['city', 'malls', 'other'].find(g => G[g]?.count) || 'city';
  const root = h('div', { class: 'pl' });

  const locBox = h('div');
  const pkgBox = h('div');
  const calcBox = h('div');
  root.append(locBox, pkgBox, calcBox);

  const groupNets = () => G[P.group]?.networks || [];
  const packages = () => cfg.groups[P.group]?.packages || [];
  const curPkg = () => packages().find(p => p.id === P.pkg) || null;
  const allKeys = () => groupNets().flatMap(n => n.addresses.map(a => key(n.index, a.i)));
  const addrIndex = () => {
    const m = new Map();
    groupNets().forEach(n => n.addresses.forEach(a => m.set(key(n.index, a.i), { n, a })));
    return m;
  };
  const locLabel = g => g === 'malls' ? T(L, 'Առևտրի կենտրոն', 'Торговый центр') : T(L, 'Խանութ', 'Магазин');

  /* ---------------------------------------------------- 1. որտեղ գովազդել */
  function drawLocs() {
    clear(locBox);
    const cityLogo = G.city?.networks?.[0]?.logo;
    const cards = [
      ['city', cityLogo ? h('img', { src: cityLogo, alt: '' }) : '🏙', T(L, 'Երևան Սիթի', 'Ереван Сити'),
        `${nf(G.city?.count || 0)} ${T(L, 'հասցե', 'адресов')}`],
      ['malls', '🏢', T(L, 'Առևտրի կենտրոններ', 'Торговые центры'), `${nf(G.malls?.count || 0)} ${T(L, 'մոլ', 'ТЦ')}`],
      ['other', '🏪', T(L, 'Այլ սուպերմարկետներ', 'Другие супермаркеты'),
        `${nf(G.other?.nets || 0)} ${T(L, 'ցանց', 'сетей')} / ${nf(G.other?.count || 0)} ${T(L, 'կետ', 'точек')}`],
    ];
    locBox.append(h('div', { class: 'card pl-hero' },
      h('h2', { class: 'pl-title', text: T(L, 'Որտեղ եք ցանկանում գովազդել', 'Где вы хотите рекламироваться') }),
      h('div', { class: 'pl-kicker', text: T(L, 'Ընտրեք վայրը՝ փաթեթները և հաշվարկը կփոխվեն', 'Выберите место — пакеты и расчёт обновятся') }),
      h('div', { class: 'pl-locs' }, ...cards.map(([g, ic, title, cnt]) => h('button', {
        class: `pl-loc g-${g}${P.group === g ? ' on' : ''}`, disabled: !G[g]?.count,
        onClick: () => { if (P.group === g) return; P.group = g; P.pkg = ''; P.sel = new Set(); drawAll(); },
      }, h('span', { class: 'pl-chev', text: P.group === g ? '✓' : '›' }),
      h('div', { class: 'pl-ico' }, ic), h('div', { class: 'pl-lt', text: title }), h('div', { class: 'pl-lc', text: cnt }))))));
  }

  /* ---------------------------------------------------- 2. հեռարձակման ծառայություն (փաթեթներ) */
  const periods = () => pl.group_periods?.[P.group] || ['month', 'half', 'year'];
  function pkgPrice(p) {
    const now = unitPrice(cfg, p, P.mode, p.price);
    const per = { month: T(L, '/ ամիս', '/ мес'), half: T(L, '/ ամիս · 6 ամսով', '/ мес · на 6 мес'),
      year: T(L, '/ ամիս · տարեկան', '/ мес · годовой') }[P.mode];
    return { now, old: now < p.price ? p.price : 0, per };
  }
  const savePct = (p, m) => (p.price ? Math.round((1 - unitPrice(cfg, p, m, p.price) / p.price) * 100) : 0);
  function drawPkgs() {
    clear(pkgBox);
    const list = packages();
    if (!periods().includes(P.mode)) P.mode = 'month';
    const best = m => Math.max(0, ...list.map(p => savePct(p, m)), list.length ? 0 : cfg.discounts[m] || 0);
    const seg = h('div', { class: 'seg' }, ...periods().map(m => [m, periodName(m)])
      .map(([m, label]) => h('button', { class: P.mode === m ? 'on' : '', onClick: () => { P.mode = m; P.period = m; drawPkgs(); drawCalc(); } },
        label, best(m) ? h('span', { class: 'pl-off', text: ` −${best(m)}%` }) : null)));
    const edit = h('button', { class: 'btn sm', onClick: () => editDialog(pl, L) }, '✏️ ' + T(L, 'Փոխել գները', 'Изменить цены'));
    const grid = h('div', { class: 'pl-pkgs' });
    list.forEach(p => {
      const pr = pkgPrice(p);
      const on = P.pkg === p.id;
      const feat = (ic, k, v) => h('div', { class: 'pl-f' }, h('span', { class: 'pl-fi', text: ic }), h('span', { class: 'pl-fk', text: k }),
        h('b', { text: v }));
      grid.append(h('div', { class: `pl-pkg${p.popular ? ' pop' : ''}${on ? ' on' : ''}` },
        p.popular ? h('div', { class: 'pl-rib', text: T(L, 'ԱՄԵՆԱՊԱՀԱՆՋՎԱԾ', 'САМЫЙ ПОПУЛЯРНЫЙ') }) : null,
        h('div', { class: 'pl-pico', text: p.icon || '⚡' }),
        h('div', { class: 'pl-pn', text: p.name }),
        h('div', { class: 'pl-line' }),
        feat('🏬', locLabel(P.group), p.locations ? String(p.locations) : `${T(L, 'բոլորը', 'все')} ${nf(G[P.group]?.count || 0)}`),
        feat('▶', T(L, 'Հեռարձակման քանակ', 'Выходов'), `${T(L, 'օրական', 'в день')} ${p.spots}`),
        feat('🎞', T(L, 'Հոլովակ', 'Ролик'), `${p.clip} ${T(L, 'վ.', 'сек')}`),
        (L ? p.note_ru || p.note : p.note) ? h('div', { class: 'pl-note', text: L ? p.note_ru || p.note : p.note }) : null,
        h('div', { class: 'pl-price' }, pr.old ? h('s', { text: money(pr.old) }) : null, h('b', { text: money(pr.now) }),
          h('span', { text: pr.per + (p.locations ? '' : T(L, ' · մեկ խանութի համար', ' · за магазин')) })),
        h('button', { class: `btn ${on || p.popular ? 'primary' : ''} block`, onClick: () => choose(p) },
          on ? '✓ ' + T(L, 'ԸՆՏՐՎԱԾ', 'ВЫБРАНО') : T(L, 'ԸՆՏՐԵԼ', 'ВЫБРАТЬ'))));
    });
    if (!list.length && P.group === 'malls') {
      groupNets().forEach(n => n.addresses.forEach(a => grid.append(h('div', { class: 'pl-pkg' },
        h('div', { class: 'pl-pico', text: '🏢' }), h('div', { class: 'pl-pn', text: a.address }),
        h('div', { class: 'pl-line' }),
        h('div', { class: 'pl-f' }, h('span', { class: 'pl-fi', text: '▶' }), h('span', { class: 'pl-fk', text: T(L, '15 եթեր/օր', '15 выходов/день') }),
          h('b', { text: a.p15 ? money(a.p15) : '—' })),
        h('div', { class: 'pl-f' }, h('span', { class: 'pl-fi', text: '▶' }), h('span', { class: 'pl-fk', text: T(L, '30 եթեր/օր', '30 выходов/день') }),
          h('b', { text: a.p30 ? money(a.p30) : '—' })),
        h('div', { class: 'tiny muted', text: T(L, 'Ամսական գինը՝ ԱԱՀ-ն ներառյալ', 'Цена за месяц, с НДС') })))));
    } else if (!list.length) grid.append(h('div', { class: 'pl-empty small muted', text: T(L,
      'Այս ցանցերի համար գործում է յուրաքանչյուր ցանցի գինը (ներքևի աղյուսակում): Հասցեները ընտրեք հաշվիչում:',
      'Для этих сетей действует цена каждой сети (таблица ниже). Адреса выберите в калькуляторе.') }));
    pkgBox.append(h('div', { class: 'card pl-svc' },
      h('div', { class: 'card-head' }, h('div', {},
        h('div', { class: 'pl-cap', text: T(L, 'ՀԵՌԱՐՁԱԿՄԱՆ ԾԱՌԱՅՈՒԹՅՈՒՆ', 'УСЛУГА ВЕЩАНИЯ') }),
        h('div', { class: 'small', text: T(L, `Հասանելի է ${pl.capacity} ընկերության համար`, `Доступно для ${pl.capacity} компаний`) }),
        h('div', { class: 'small', style: 'color:var(--blue);font-weight:700', text: T(L, 'Ամրագրեք Ձեր տեղը այսօր 📌', 'Забронируйте место сегодня 📌') })),
      h('div', { class: 'right' }, seg, edit)),
      grid,
      h('div', { class: 'pl-support tiny muted', text: '🛠 ' + T(L, 'Տեխնիկական աջակցություն՝ ամբողջ ժամկետում', 'Техническая поддержка — весь срок') })));
  }
  function choose(p) {
    if (P.pkg === p.id) { P.pkg = ''; drawAll(); return; }
    P.pkg = p.id;
    if (!p.locations) P.sel = new Set(allKeys());          // «բոլոր մասնաճյուղերը» փաթեթ
    P.period = P.mode;
    drawAll();
    calcBox.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* ---------------------------------------------------- 3. կանխատեսվող արդյունքներ */
  // նույնը, ինչ pricecalc.estimate
  function totals() {
    if (!periods().includes(P.period)) P.period = 'month';
    const months = PERIOD_MONTHS[P.period];
    const pkg = curPkg();
    const idx = addrIndex();
    const rows = [...P.sel].map(k => {
      const x = idx.get(k);
      if (!x) return null;
      if ('p15' in x.a) {
        const spots = P.spots.get(k) === 30 ? 30 : 15;
        const month = spots === 30 ? x.a.p30 : x.a.p15;
        return { ...x, k, spots, month, unit: unitPrice(cfg, null, P.period, month) };
      }
      const month = pkg ? pkg.price : (x.a.price || 0);
      return { ...x, k, spots: pkg ? pkg.spots : cfg.spots, month, unit: unitPrice(cfg, pkg, P.period, month) };
    }).filter(Boolean);
    const subtotal = rows.reduce((s, x) => s + x.month, 0) * months;
    const broadcast = rows.reduce((s, x) => s + x.unit, 0) * months;
    const discount = subtotal - broadcast;
    const studio = cfg.studio.filter(s => P.studio.has(s.id));
    const studioSum = studio.reduce((s, x) => s + x.price, 0);
    const spots = rows[0]?.spots || (pkg ? pkg.spots : cfg.spots);
    const airings = rows.reduce((s, x) => s + x.spots, 0) * months * pl.days_in_month;
    return { months, pkg, rows, subtotal, broadcast, pct: subtotal ? Math.round(discount * 100 / subtotal) : 0, discount,
      studio, studioSum, spots, airings, total: broadcast + studioSum, perSpot: airings ? Math.round(broadcast / airings) : 0,
      noPrice: rows.filter(x => !x.month).length };
  }
  const periodName = p => ({ month: T(L, 'Ամսական', 'Месячно'), half: T(L, '6 ամսով', 'На 6 месяцев'), year: T(L, 'Տարեկան', 'Годовой') })[p];

  function drawCalc() {
    clear(calcBox);
    const seg = h('div', { class: 'seg' }, ...periods().map(p => h('button', {
      class: P.period === p ? 'on' : '', onClick: () => { P.period = p; P.mode = p; drawPkgs(); drawCalc(); },
    }, periodName(p))));
    const brand = h('input', { type: 'text', value: P.brand, placeholder: T(L, 'օր.՝ Mix Media, Yoga', 'напр.: Mix Media, Yoga') });
    const contact = h('input', { type: 'text', value: P.contact, placeholder: T(L, 'Անուն, հեռախոս', 'Имя, телефон') });
    brand.addEventListener('input', () => { P.brand = brand.value; });
    contact.addEventListener('input', () => { P.contact = contact.value; });

    const chosen = h('div', { class: 'pl-chosen' });
    const tiles = h('div', { class: 'grid c2', style: 'margin:12px 0' });
    const totalBox = h('div', { class: 'pl-total' });
    const studioBox = h('div', { class: 'grid c2' });
    const resultBox = h('div', { style: 'margin-top:12px' });

    // հասցեների ընտրություն
    const addrList = h('div', { class: 'pl-addrs' });
    const q = h('input', { type: 'search', value: P.q, placeholder: T(L, 'Որոնել հասցե կամ ցանց…', 'Поиск адреса или сети…') });
    const selAll = h('button', { class: 'btn sm', onClick: () => { visibleKeys().forEach(k => P.sel.add(k)); drawAddrs(); update(); } },
      T(L, 'Նշել բոլորը', 'Отметить все'));
    const selNone = h('button', { class: 'btn sm ghost', onClick: () => { P.sel.clear(); drawAddrs(); update(); } }, t('btn.none'));
    const norm = s => String(s || '').toLowerCase().replace(/[․.,:;«»"'()\-–—/]+/g, ' ').replace(/\s+/g, ' ').trim();
    const visible = () => {
      const needle = norm(P.q);
      return groupNets().map(n => ({ n, list: n.addresses.filter(a => !needle || norm(`${n.short} ${a.address}`).includes(needle)) }))
        .filter(x => x.list.length);
    };
    const visibleKeys = () => visible().flatMap(x => x.list.map(a => key(x.n.index, a.i)));
    function drawAddrs() {
      clear(addrList);
      const pkg = curPkg();
      visible().forEach(({ n, list }) => {
        const keys = list.map(a => key(n.index, a.i));
        const all = keys.every(k => P.sel.has(k));
        const netCb = h('input', { type: 'checkbox', checked: all });
        netCb.addEventListener('change', () => { keys.forEach(k => (netCb.checked ? P.sel.add(k) : P.sel.delete(k))); drawAddrs(); update(); });
        addrList.append(h('label', { class: 'pl-net' }, netCb,
          n.logo ? h('img', { src: n.logo, alt: '' }) : null, h('b', { text: n.short }),
          h('span', { class: 'tiny muted', text: `${list.length} ${T(L, 'հասցե', 'адр.')}` }),
          !pkg && P.group !== 'malls' ? h('span', { class: 'tiny', style: 'margin-left:auto;color:var(--violet);font-weight:700',
            text: n.price ? `${money(n.price)} / ${T(L, 'ամիս', 'мес')}` : T(L, 'գին չկա', 'нет цены') }) : null));
        const grid = h('div', { class: 'pl-agrid' });
        list.forEach(a => {
          const k = key(n.index, a.i);
          const cb = h('input', { type: 'checkbox', checked: P.sel.has(k) });
          cb.addEventListener('change', () => { cb.checked ? P.sel.add(k) : P.sel.delete(k); update(); });
          let spotSel = null;
          if ('p15' in a) {
            spotSel = h('select', { style: 'margin-left:auto;width:auto' }, ...[15, 30].map(s => h('option', { value: String(s),
              selected: (P.spots.get(k) || 15) === s, text: `${s} ${T(L, 'եթեր/օր', 'вых./день')} · ${money(s === 30 ? a.p30 : a.p15)}` })));
            spotSel.addEventListener('click', e => e.preventDefault());
            spotSel.addEventListener('change', () => { P.spots.set(k, Number(spotSel.value)); P.sel.add(k); cb.checked = true; update(); });
          }
          grid.append(h('label', { class: `pl-a${a.free === 0 ? ' full' : ''}`, title: a.free === 0 ? T(L, 'Տեղ չկա', 'Мест нет') : '' }, cb,
            h('span', { text: a.address }), spotSel));
        });
        addrList.append(grid);
      });
      if (!addrList.children.length) addrList.append(h('div', { class: 'small muted', text: T(L, 'Ոչինչ չգտնվեց', 'Ничего не найдено') }));
    }
    q.addEventListener('input', debounce(() => { P.q = q.value; drawAddrs(); }, 200));

    cfg.studio.forEach(s => {
      const cb = h('input', { type: 'checkbox', checked: P.studio.has(s.id) });
      cb.addEventListener('change', () => { cb.checked ? P.studio.add(s.id) : P.studio.delete(s.id); update(); });
      studioBox.append(h('label', { class: 'pl-studio' }, cb, h('span', { text: L ? s.name_ru || s.name : s.name }),
        h('b', { text: `+${money(s.price)}` })));
    });

    function update() {
      const r = totals();
      clear(chosen).append(r.pkg || r.rows.length
        ? h('div', { class: 'row tight' },
          h('span', { class: 'badge plain', text: `📍 ${({ city: T(L, 'Երևան Սիթի', 'Ереван Сити'), malls: T(L, 'Առևտրի կենտրոններ', 'Торговые центры'), other: T(L, 'Այլ սուպերմարկետներ', 'Другие супермаркеты') })[P.group]}` }),
          r.pkg ? h('span', { class: 'badge ok', text: `${r.pkg.icon} ${r.pkg.name} · ${money(unitPrice(cfg, r.pkg, P.period, r.pkg.price))} / ${T(L, 'ամիս', 'мес')}` })
            : P.group === 'malls' ? h('span', { class: 'badge plain', text: T(L, 'Մոլի գնով', 'По цене ТЦ') })
              : h('span', { class: 'badge warn', text: T(L, 'Փաթեթ ընտրված չէ՝ ցանցի գնով', 'Пакет не выбран — по цене сети') }),
          h('span', { class: 'badge plain', text: `${r.spots} ${T(L, 'սփոթ/օր', 'выходов/день')}` }))
        : h('div', { class: 'muted', text: '—' }));
      clear(tiles).append(
        h('div', { class: 'tile pl-k' }, h('div', { class: 'k', text: T(L, 'Ընդհանուր եթերներ', 'Всего выходов') }),
          h('div', { class: 'v', text: nf(r.airings) }),
          h('div', { class: 'n', text: `${r.perSpot ? `1 ${T(L, 'եթեր', 'выход')} = ${money(r.perSpot)} · ` : ''}${r.months * pl.days_in_month} ${T(L, 'օր', 'дн.')}` })),
        h('div', { class: 'tile pl-k' }, h('div', { class: 'k', text: T(L, 'Ընտրված հասցեներ', 'Выбрано адресов') }),
          h('div', { class: 'v', style: 'color:var(--pink)', text: nf(r.rows.length) }),
          h('div', { class: 'n', text: r.noPrice ? `⚠ ${r.noPrice} ${T(L, 'հասցեի գինը նշված չէ', 'адр. без цены')}` : '' })));
      clear(totalBox).append(
        h('div', { class: 'pl-cap', text: T(L, 'ԸՆԴԱՄԵՆԸ (ԶԵՂՉԸ ՆԵՐԱՌՅԱԼ)', 'ИТОГО (СО СКИДКОЙ)') }),
        h('div', { class: 'pl-sum', text: money(r.total) }),
        h('div', { class: 'tiny muted', text: [periodName(P.period),
          r.subtotal ? `${money(r.subtotal)}${r.discount ? ` − ${r.pct}% (${money(r.discount)})` : ''}` : '',
          r.studioSum ? `+ ${T(L, 'ստուդիա', 'студия')} ${money(r.studioSum)}` : ''].filter(Boolean).join(' · ') }));
      selCount.textContent = `${r.rows.length}`;
    }
    const selCount = h('b', { text: '0' });

    // կոճակներ
    const shareText = () => {
      const r = totals();
      const g = ({ city: 'Երևան Սիթի', malls: T(L, 'Առևտրի կենտրոններ', 'Торговые центры'), other: T(L, 'Այլ սուպերմարկետներ', 'Другие супермаркеты') })[P.group];
      return [`Mix Media · ${T(L, 'Կանխատեսվող արդյունքներ', 'Расчёт размещения')}`,
        P.brand ? `${T(L, 'Բրենդ', 'Бренд')}: ${P.brand}` : '', P.contact ? `${T(L, 'Կոնտակտ', 'Контакт')}: ${P.contact}` : '',
        `${T(L, 'Վայր', 'Место')}: ${g}`, `${T(L, 'Ժամկետ', 'Срок')}: ${periodName(P.period)} (${r.months} ${T(L, 'ամիս', 'мес.')})`,
        r.pkg ? `${T(L, 'Փաթեթ', 'Пакет')}: ${r.pkg.name}` : '',
        `${T(L, 'Հասցեներ', 'Адреса')}: ${r.rows.length}${r.rows.length && r.rows.length <= 8 ? ' — ' + r.rows.map(x => x.a.address).join('; ') : ''}`,
        `${T(L, 'Ընդհանուր եթերներ', 'Всего выходов')}: ${nf(r.airings)}`,
        r.studio.length ? `${T(L, 'Ստուդիա', 'Студия')}: ${r.studio.map(s => (L ? s.name_ru || s.name : s.name)).join(', ')}` : '',
        `${T(L, 'Ընդամենը', 'Итого')}: ${money(r.total)}`, `📞 ${cfg.phone}`].filter(Boolean).join('\n');
    };
    const phoneDigits = s => {
      let d = String(s || '').replace(/\D/g, '');
      if (d.length === 9 && d.startsWith('0')) d = '374' + d.slice(1);
      if (d.length === 8) d = '374' + d;
      return d.length >= 11 ? d : '';
    };
    const need = () => {
      if (!P.sel.size) { toast(T(L, 'Ընտրեք գոնե մեկ հասցե', 'Выберите хотя бы один адрес'), 'warn'); return false; }
      return true;
    };
    const tg = h('button', { class: 'btn pl-tg', onClick: () => { if (!need()) return;
      window.open(`https://t.me/share/url?url=${encodeURIComponent('https://mix-media.am/price/')}&text=${encodeURIComponent(shareText())}`, '_blank', 'noopener'); } },
    '✈️ TELEGRAM');
    const wa = h('button', { class: 'btn pl-wa', onClick: () => { if (!need()) return;
      window.open(`https://wa.me/${phoneDigits(P.contact)}?text=${encodeURIComponent(shareText())}`, '_blank', 'noopener'); } },
    '💬 WHATSAPP');
    const dl = h('button', { class: 'btn', onClick: async () => {
      if (!need()) return;
      loader(true, T(L, 'Պատրաստում եմ ֆայլը…', 'Готовлю файл…'));
      try {
        const r = await api('/api/stores/estimate', { method: 'POST', body: { group: P.group, package: P.pkg, period: P.period,
          brand: P.brand, contact: P.contact, studio: [...P.studio],
          addresses: [...P.sel].map(k => { const [net, i] = k.split(':').map(Number); return { net, i, spots: P.spots.get(k) || 15 }; }) } });
        clear(resultBox).append(filesResult([r.file]));
        window.open(r.file.url, '_blank');
      } catch (e) { /* toast */ } finally { loader(false); }
    } }, '📄 ' + T(L, 'ՆԵՐԲԵՌՆԵԼ ՖԱՅԼԸ', 'СКАЧАТЬ ФАЙЛ'));
    const consult = h('button', { class: 'btn pl-cons', onClick: () => consultDialog(cfg, L, shareText) },
      '📞 ' + T(L, 'ԽՈՐՀՐԴԱՏՎՈՒԹՅՈՒՆ', 'КОНСУЛЬТАЦИЯ'));

    calcBox.append(h('div', { class: 'card pl-calc' },
      h('div', { class: 'card-head' }, h('div', { class: 'pl-cap', text: T(L, 'ԿԱՆԽԱՏԵՍՎՈՂ ԱՐԴՅՈՒՆՔՆԵՐ', 'ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ') }),
        h('div', { class: 'right' }, seg)),
      h('div', { class: 'grid c2' }, field(T(L, 'Ձեր բրենդը', 'Ваш бренд'), brand), field(T(L, 'Կոնտակտ', 'Контакт'), contact)),
      chosen,
      h('details', { class: 'pl-pick', open: true },
        h('summary', {}, '📍 ', T(L, 'Հասցեներ', 'Адреса'), ' · ', selCount, ' ', T(L, 'ընտրված', 'выбрано')),
        h('div', { class: 'row', style: 'margin:8px 0' }, h('div', { class: 'search', style: 'flex:1;min-width:200px' }, q), selAll, selNone),
        addrList),
      tiles,
      h('div', { class: 'pl-cap', style: 'margin:4px 0 8px', text: T(L, 'ՍՏՈՒԴԻԱՅԻՆ ԾԱՌԱՅՈՒԹՅՈՒՆՆԵՐ', 'УСЛУГИ СТУДИИ') }),
      studioBox,
      totalBox,
      h('div', { class: 'pl-btns' }, tg, wa, dl, consult),
      resultBox));
    drawAddrs();
    update();
  }

  function drawAll() { drawLocs(); drawPkgs(); drawCalc(); }
  drawAll();
  return root;
}

/* ---------------------------------------------------- 📞 խորհրդատվություն */
function consultDialog(cfg, L, shareText) {
  const tel = String(cfg.phone || '').replace(/[^\d+]/g, '');
  modal({ title: '📞 ' + T(L, 'Խորհրդատվություն', 'Консультация'), body: h('div', {},
    h('p', { class: 'small muted', text: T(L, 'Զանգահարեք կամ գրեք՝ կպատասխանենք բոլոր հարցերին:', 'Позвоните или напишите — ответим на все вопросы.') }),
    h('div', { class: 'list' },
      h('a', { class: 'li', href: `tel:${tel}` }, h('b', { text: '📞 ' + cfg.phone })),
      cfg.whatsapp ? h('a', { class: 'li', href: `https://wa.me/${cfg.whatsapp}`, target: '_blank', rel: 'noopener' }, h('b', { text: '💬 WhatsApp' })) : null,
      cfg.telegram ? h('a', { class: 'li', href: `https://t.me/${cfg.telegram}`, target: '_blank', rel: 'noopener' }, h('b', { text: `✈️ Telegram @${cfg.telegram}` })) : null,
      h('a', { class: 'li', href: 'mailto:info@mix-media.am' }, h('b', { text: '✉️ info@mix-media.am' })))),
  actions: [{ label: '📋 ' + T(L, 'Պատճենել հաշվարկը', 'Копировать расчёт'), onClick: () => { copyText(shareText()); return false; } },
    { label: t('btn.close'), primary: true }] });
}

/* ---------------------------------------------------- ✏️ գների խմբագրում */
function editDialog(pl, L) {
  const cfg = JSON.parse(JSON.stringify(pl.config));
  const body = h('div');
  let tab = P.group || 'malls';
  const titles = { city: T(L, 'Երևան Սիթի', 'Ереван Сити'), malls: T(L, 'Առևտրի կենտրոններ', 'Торговые центры'), other: T(L, 'Այլ սուպերմարկետներ', 'Другие') };
  const num = (v, w = '110px') => h('input', { type: 'text', inputmode: 'numeric', value: String(v ?? ''), style: `width:${w}` });

  function draw() {
    clear(body);
    const tabs = h('div', { class: 'seg', style: 'margin-bottom:12px;flex-wrap:wrap' }, ...Object.keys(titles).map(g =>
      h('button', { class: tab === g ? 'on' : '', onClick: () => { tab = g; draw(); } }, titles[g])));
    const list = cfg.groups[tab].packages;
    const rows = h('div', { class: 'list' });
    list.forEach((p, i) => {
      const f = { icon: h('input', { type: 'text', value: p.icon || '', style: 'width:52px' }), name: h('input', { type: 'text', value: p.name }),
        price: num(p.price), half: num(p.half || '', '100px'), year: num(p.year || '', '100px'), locations: num(p.locations, '70px'), spots: num(p.spots, '70px'), clip: num(p.clip, '70px'),
        popular: h('input', { type: 'checkbox', checked: !!p.popular }), note: h('input', { type: 'text', value: p.note || '' }),
        note_ru: h('input', { type: 'text', value: p.note_ru || '' }) };
      Object.entries(f).forEach(([k, el]) => el.addEventListener(el.type === 'checkbox' ? 'change' : 'input', () => {
        p[k] = el.type === 'checkbox' ? el.checked : el.value;
      }));
      rows.append(h('div', { class: 'li', style: 'flex-wrap:wrap;align-items:flex-end' },
        field(T(L, 'Նշան', 'Иконка'), f.icon), h('div', { style: 'flex:1;min-width:120px' }, field(T(L, 'Անուն', 'Название'), f.name)),
        field(T(L, 'Ամսական ֏ (1 հասցե)', 'Месячно ֏ (1 адрес)'), f.price),
        field(T(L, '6 ամսով ֏/ամիս', 'На 6 мес ֏/мес'), f.half), field(T(L, 'Տարեկան ֏/ամիս', 'Годовой ֏/мес'), f.year),
        field(T(L, 'Հասցե (0՝ բոլորը)', 'Адресов (0 — все)'), f.locations), field(T(L, 'Սփոթ/օր', 'Выходов/день'), f.spots),
        field(T(L, 'Հոլովակ, վ.', 'Ролик, сек'), f.clip),
        h('label', { class: 'check', style: 'margin-bottom:10px' }, f.popular, T(L, 'Ամենապահանջված', 'Популярный')),
        h('div', { style: 'flex:1;min-width:180px' }, field(T(L, 'Նշում (հայ.)', 'Примечание (арм.)'), f.note)),
        h('div', { style: 'flex:1;min-width:180px' }, field(T(L, 'Նշում (ռուս.)', 'Примечание (рус.)'), f.note_ru)),
        h('button', { class: 'btn sm ghost danger', style: 'margin-bottom:10px', onClick: () => { list.splice(i, 1); draw(); } }, '🗑')));
    });
    const add = h('button', { class: 'btn sm', onClick: () => { list.push({ id: '', name: 'New', icon: '⚡', price: 0, locations: 1, spots: cfg.spots, clip: cfg.clip, popular: false }); draw(); } },
      '➕ ' + T(L, 'Ավելացնել փաթեթ', 'Добавить пакет'));

    const disc = h('div', { class: 'row' });
    [['month', T(L, 'Ամսական', 'Месяц')], ['half', T(L, '6 ամիս', '6 месяцев')], ['year', T(L, 'Տարեկան', 'Год')]].forEach(([k, label]) => {
      const inp = num(cfg.discounts[k], '70px');
      inp.addEventListener('input', () => { cfg.discounts[k] = inp.value; });
      disc.append(field(`${label}, ${T(L, 'զեղչ %', 'скидка %')}`, inp));
    });
    const studio = h('div', { class: 'list' });
    cfg.studio.forEach((s, i) => {
      const n1 = h('input', { type: 'text', value: s.name }), n2 = h('input', { type: 'text', value: s.name_ru || '' }), pr = num(s.price);
      n1.addEventListener('input', () => { s.name = n1.value; });
      n2.addEventListener('input', () => { s.name_ru = n2.value; });
      pr.addEventListener('input', () => { s.price = pr.value; });
      studio.append(h('div', { class: 'li', style: 'flex-wrap:wrap;align-items:flex-end' },
        h('div', { style: 'flex:1;min-width:140px' }, field(T(L, 'Անուն (հայ.)', 'Название (арм.)'), n1)),
        h('div', { style: 'flex:1;min-width:140px' }, field(T(L, 'Անուն (ռուս.)', 'Название (рус.)'), n2)),
        field('֏', pr), h('button', { class: 'btn sm ghost danger', style: 'margin-bottom:10px', onClick: () => { cfg.studio.splice(i, 1); draw(); } }, '🗑')));
    });
    const addS = h('button', { class: 'btn sm', onClick: () => { cfg.studio.push({ id: `s${Date.now() % 100000}`, name: '', name_ru: '', price: 0 }); draw(); } },
      '➕ ' + T(L, 'Ավելացնել ծառայություն', 'Добавить услугу'));
    const contacts = h('div', { class: 'grid c3' });
    [['phone', T(L, 'Հեռախոս', 'Телефон')], ['whatsapp', 'WhatsApp (37444…)'], ['telegram', 'Telegram (@…)']].forEach(([k, label]) => {
      const inp = h('input', { type: 'text', value: cfg[k] || '' });
      inp.addEventListener('input', () => { cfg[k] = inp.value.replace(/^@/, ''); });
      contacts.append(field(label, inp));
    });
    const malls = h('div', { class: 'list' });
    if (tab === 'malls') {
      cfg.mall_prices = cfg.mall_prices || {};
      (pl.groups.malls?.networks || []).forEach(n => n.addresses.forEach(a => {
        const cur = cfg.mall_prices[a.address] || (cfg.mall_prices[a.address] = { p15: a.p15, p30: a.p30 });
        const i15 = num(cur.p15), i30 = num(cur.p30);
        i15.addEventListener('input', () => { cur.p15 = i15.value; });
        i30.addEventListener('input', () => { cur.p30 = i30.value; });
        malls.append(h('div', { class: 'li', style: 'flex-wrap:wrap;align-items:flex-end' },
          h('b', { style: 'flex:1;min-width:160px;margin-bottom:12px', text: `🏢 ${a.address}` }),
          field(T(L, '15 եթեր/օր ֏/ամիս', '15 вых./день ֏/мес'), i15), field(T(L, '30 եթեր/օր ֏/ամիս', '30 вых./день ֏/мес'), i30)));
      }));
    }
    body.append(tabs,
      tab === 'malls' ? h('h3', { text: '🏢 ' + T(L, 'Մոլերի գները (ԱԱՀ-ն ներառյալ)', 'Цены ТЦ (с НДС)') }) : null, tab === 'malls' ? malls : null,
      h('h3', { text: '📦 ' + T(L, 'Փաթեթներ', 'Пакеты') + ' · ' + titles[tab] }),
      h('div', { class: 'tiny muted', text: T(L, '6 ամսով / Տարեկան՝ ամսական գինը այդ պայմանագրով. դատարկ՝ ամսականից զեղչով (ներքևում):',
        'На 6 мес / Годовой — цена за месяц при таком договоре; пусто — месячная со скидкой (ниже).') }),
      rows, h('div', { class: 'row', style: 'margin:8px 0 16px' }, add),
      h('h3', { text: '🏷 ' + T(L, 'Զեղչեր ըստ ժամկետի', 'Скидки по сроку') }), disc,
      h('h3', { text: '🎙 ' + T(L, 'Ստուդիայի ծառայություններ', 'Услуги студии') }), studio, h('div', { class: 'row', style: 'margin:8px 0 16px' }, addS),
      h('h3', { text: '📞 ' + T(L, 'Կոնտակտներ (կոճակների համար)', 'Контакты (для кнопок)') }), contacts);
    if (cfg.updated) body.append(h('div', { class: 'tiny muted', style: 'margin-top:10px',
      text: `${T(L, 'Վերջին փոփոխությունը', 'Изменено')}: ${String(cfg.updated).replace('T', ' ')} · ${cfg.updated_by || ''}` }));
  }
  draw();
  modal({ title: '✏️ ' + T(L, 'Գնացուցակ', 'Прайс-лист'), wide: true, body,
    actions: [{ label: t('btn.cancel') }, { label: '💾 ' + t('btn.save'), primary: true, onClick: async () => {
      try {
        loader(true);
        await api('/api/stores/pricelist', { method: 'POST', body: cfg });
        toast(t('msg.saved'), 'ok');
        window.MM.reload();
      } catch (e) { return false; } finally { loader(false); }
    } }] });
}
