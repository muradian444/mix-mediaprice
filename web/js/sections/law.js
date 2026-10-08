// ⚖️ Իրավաբան՝ ֆայլերի խիստ համեմատում (նույնիսկ 1 տառ, բացատ, անտեսանելի նշան)
import { S, api, clear, emptyBox, filesResult, h, loader, nf, t, toast } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Сравнение документов до символа'
  : 'Փաստաթղթերի համեմատում՝ մինչև նշան';

const ICON = { change: '✏️', delete: '❌', insert: '➕', format: '🎨' };

export async function render() {
  const L = S.lang === 'ru' ? 1 : 0;
  const box = h('div');
  const result = h('div');
  const fmts = (S.meta.law_formats || []).join(', ');

  box.append(h('div', { class: 'card' },
    h('h2', { text: '⚖️ ' + (L ? 'Юрист' : 'Իրավաբան') }), h('div', { class: 'gradline' }),
    h('p', { class: 'small', text: L
      ? 'Приложение сравнивает файлы очень внимательно и показывает КАЖДОЕ изменение: даже одну букву, цифру, '
        + 'пробел, знак, невидимый символ или формат (жирный/курсив).'
      : 'Հավելվածը շատ ուշադիր համեմատում է ֆայլերը և ցույց է տալիս ԱՄԵՆ փոփոխություն՝ նույնիսկ 1 տառ, թիվ, '
        + 'բացատ, նշան, անտեսանելի նշան կամ ձևաչափ (թավ/շեղ):' }),
    h('p', { class: 'tiny muted', text: (L ? 'Форматы: ' : 'Ձևաչափեր՝ ') + fmts
      + (L ? ' · а также 📷 фото подписанного договора (текст распознаётся и сравнивается с оригиналом)'
        : ' · ինչպես նաև 📷 ստորագրված պայմանագրի նկար (տեքստը ճանաչվում և համեմատվում է բնօրինակի հետ)') })));

  const auto = card(L ? '🔎 Автоматически' : '🔎 Ավտոմատ',
    L ? 'Пришлите проверяемый файл — оригинал найдётся сам (из созданных договоров, шаблонов и хранилища).'
      : 'Ուղարկեք ստուգվող ֆայլը՝ բնօրինակը կգտնվի ինքնաբերաբար (պատրաստված պայմանագրերից, շաբլոններից, պահոցից):');
  const autoInput = h('input', { type: 'file', style: 'display:none' });
  const autoBtn = h('button', { class: 'btn primary' }, '📎 ' + (L ? 'Выбрать файл' : 'Ընտրել ֆայլը'));
  autoBtn.addEventListener('click', () => autoInput.click());
  autoInput.addEventListener('change', async () => {
    if (!autoInput.files.length) return;
    const fd = new FormData(); fd.append('file', autoInput.files[0]);
    loader(true, L ? 'Ищу оригинал и сравниваю…' : 'Փնտրում եմ բնօրինակը և համեմատում…');
    try {
      const res = await api('/api/law/auto', { method: 'POST', form: fd });
      if (res.ok === false) {
        clear(result).append(h('div', { class: 'card' },
          h('h3', { text: '🤔 ' + res.detail }),
          res.candidates?.length ? h('div', { class: 'list' }, ...res.candidates.map(c =>
            h('div', { class: 'li' }, h('div', { class: 't' }, h('b', { text: c.name }),
              h('div', { class: 's', text: `${L ? 'похожесть' : 'նմանություն'} ${c.score}%` })),
            h('button', { class: 'btn sm', onClick: () => compareWith(c.path, res.checked_path, L, result) }, t('btn.search'))))) : null));
        return;
      }
      clear(result).append(resultCard(res, L));
    } finally { loader(false); autoInput.value = ''; }
  });
  auto.append(h('div', { class: 'row' }, autoBtn, autoInput));

  const two = card(L ? '📂 Два файла' : '📂 Երկու ֆայլ',
    L ? 'Оригинал (как было) и изменённый файл.' : 'Բնօրինակը (ինչ եղել է) և փոփոխված ֆայլը:');
  const fa = h('input', { type: 'file' });
  const fb = h('input', { type: 'file' });
  const cmp = h('button', { class: 'btn primary' }, '⚖️ ' + (L ? 'Сравнить' : 'Համեմատել'));
  cmp.addEventListener('click', async () => {
    if (!fa.files.length || !fb.files.length) { toast(L ? 'Нужны оба файла' : 'Պետք են երկու ֆայլ', 'err'); return; }
    const fd = new FormData();
    fd.append('original', fa.files[0]); fd.append('changed', fb.files[0]); fd.append('remember', 'true');
    loader(true, L ? 'Сравниваю…' : 'Համեմատում եմ՝ տառ առ տառ…');
    try { clear(result).append(resultCard(await api('/api/law/compare', { method: 'POST', form: fd }), L)); }
    finally { loader(false); }
  });
  two.append(h('div', { class: 'grid c2' },
    h('div', { class: 'field' }, h('label', { text: (L ? '1. Оригинал' : '1. Բնօրինակ') }), fa),
    h('div', { class: 'field' }, h('label', { text: (L ? '2. Изменённый' : '2. Փոփոխված') }), fb)),
  h('div', { class: 'row' }, cmp));

  box.append(h('div', { class: 'grid c2' }, auto, two), result);
  return box;
}

function card(title, note) {
  return h('div', { class: 'card' }, h('h3', { text: title }), h('p', { class: 'small muted', text: note }));
}

async function compareWith(original, checked, L, result) {
  loader(true);
  try { clear(result).append(resultCard(await api('/api/law/compare-with', { method: 'POST', body: { original, checked } }), L)); }
  finally { loader(false); }
}

function resultCard(res, L) {
  const s = res.stats;
  const box = h('div');
  const head = h('div', { class: 'card' },
    h('div', { class: 'card-head' }, h('h2', { text: '⚖️ ' + (L ? 'Результат' : 'Արդյունք') }),
      h('div', { class: 'right' }, h('span', { class: 'badge plain', text: `${L ? 'похожесть' : 'նմանություն'} ${s.similarity}%` }))),
    h('div', { class: 'small muted' }, `📄 ${L ? 'Оригинал' : 'Բնօրինակ'}: ${res.original}`),
    h('div', { class: 'small muted' }, `📄 ${L ? 'Проверяемый' : 'Ստուգվող'}: ${res.checked}`),
    h('div', { class: 'tiny muted', style: 'margin-bottom:10px' }, `🔍 ${res.mode}`));
  if (!res.total) {
    head.append(h('div', { class: 'badge ok', style: 'font-size:13px;padding:8px 14px',
      text: (L ? '✅ Разницы нет — не изменился ни один символ' : '✅ Տարբերություն ՉԿԱ՝ ոչ մի նշան չի փոխվել') }));
  } else {
    head.append(h('div', { class: 'grid c4' },
      tl(L ? 'Всего' : 'Ընդամենը', nf(res.total)), tl(L ? 'Изменено' : 'Փոխված', nf(s.changed)),
      tl(L ? 'Удалено' : 'Ջնջված', nf(s.deleted)), tl(L ? 'Добавлено' : 'Ավելացված', nf(s.inserted)),
      tl(L ? 'Формат' : 'Ձևաչափ', nf(s.formatted)), tl(L ? '⚠️ Важные' : '⚠️ Կարևոր', nf(s.important))));
  }
  if (res.score) head.append(h('div', { class: 'tiny muted', style: 'margin-top:8px',
    text: `${L ? 'Оригинал найден автоматически' : 'Բնօրինակը գտնվել է ավտոմատ'} · ${res.score}%` }));
  if (res.candidates?.length) {
    const alt = h('div', { class: 'row', style: 'margin-top:10px' },
      h('span', { class: 'tiny muted', text: L ? 'Другой оригинал:' : 'Այլ բնօրինակ՝' }));
    res.candidates.slice(0, 4).forEach(c => alt.append(h('button', {
      class: 'btn sm', onClick: () => compareWith(c.path, res.checked_path, L, box.parentElement || box),
    }, `${c.name} · ${c.score}%`)));
    head.append(alt);
  }
  box.append(head);
  if (res.files?.length) box.append(filesResult(res.files));

  if (res.total) {
    const list = h('div', { class: 'card' });
    const onlyImp = h('label', { class: 'check' }, h('input', { type: 'checkbox' }),
      (L ? 'Только важные (числа, суммы, сроки)' : 'Միայն կարևորները (թվեր, գումարներ, ժամկետներ)'));
    const items = h('div');
    const draw = () => {
      clear(items);
      const rows = res.changes.filter(c => !onlyImp.firstChild.checked || c.important);
      if (!rows.length) items.append(emptyBox(L ? 'Нет таких изменений' : 'Այդպիսի փոփոխություն չկա', '✅'));
      rows.slice(0, 200).forEach(c => items.append(changeRow(c, L)));
      if (rows.length > 200) items.append(h('p', { class: 'small muted',
        text: `… ${L ? 'ещё' : 'ևս'} ${rows.length - 200} — ${L ? 'смотрите PDF' : 'տես PDF'}` }));
    };
    onlyImp.firstChild.addEventListener('change', draw);
    list.append(h('div', { class: 'card-head' }, h('h3', { text: (L ? 'Изменения' : 'Փոփոխությունները') }),
      h('div', { class: 'right' }, onlyImp)), items);
    draw();
    box.append(list);
    if (res.truncated) box.append(h('p', { class: 'small muted',
      text: `${L ? 'Показаны первые 400 изменений, полный список — в PDF' : 'Ցուցադրված են առաջին 400 փոփոխությունները, ամբողջը՝ PDF-ում'}` }));
  }
  return box;
}

function changeRow(c, L) {
  const node = h('div', { class: 'chg ' + c.kind });
  node.append(h('div', { class: 'ch' }, h('span', { text: `${ICON[c.kind] || '•'} ${c.n}` }),
    c.important ? h('span', { class: 'badge err', text: '⚠️' }) : null,
    h('span', { class: 'cw', text: c.where })));
  if (c.kind === 'change' && c.html) node.append(h('div', { class: 'diff', html: c.html }));
  else if (c.kind === 'delete') node.append(h('div', { class: 'diff' }, h('s', { text: c.old })));
  else if (c.kind === 'insert') node.append(h('div', { class: 'diff' }, h('b', {}, h('u', { text: c.new }))));
  else node.append(h('div', { class: 'small muted', text: c.old }));
  const details = [...(c.details || []), ...(c.fmt || [])];
  if (details.length) node.append(h('ul', {}, ...details.map(d => h('li', { text: d }))));
  return node;
}
const tl = (k, v) => h('div', { class: 'tile plain' }, h('div', { class: 'k', text: k }), h('div', { class: 'v', text: v }));
