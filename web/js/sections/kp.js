// 💼 ԿՊ (առևտրային առաջարկ)՝ 5 տեսակ, նմուշներով և լրացվող դաշտերով (+ 📷 լուսանկարից, ✏️ պահվածից)
import { S, api, clear, field, filesResult, h, loader, photoButton, setField, t, toast } from '../core.js';

export const sub = () => S.lang === 'ru' ? '5 готовых типов предложения → PDF'
  : '5 պատրաստի տեսակ → PDF';

export async function render(params) {
  const L = S.lang === 'ru' ? 1 : 0;
  const kinds = S.meta.kp || {};
  if (!params.kind || !kinds[params.kind]) {
    const box = h('div');
    const samples = h('div');
    const btn = h('button', { class: 'btn' }, '👁 ' + (L ? 'Показать 5 образцов (PDF)' : 'Ցույց տալ 5 նմուշը (PDF)'));
    btn.addEventListener('click', async () => {
      loader(true, L ? 'Готовлю образцы…' : 'Պատրաստում եմ նմուշները…');
      try {
        const r = await api('/api/kp/samples', { method: 'POST', body: {} });
        clear(samples).append(filesResult(r.files));
      } finally { loader(false); }
    });
    box.append(h('div', { class: 'card' },
      h('div', { class: 'card-head' }, h('h2', { text: L ? 'Выберите тип предложения' : 'Ընտրեք առաջարկի տեսակը' }),
        h('div', { class: 'right' }, btn)),
      h('div', { class: 'gradline' }),
      h('div', { class: 'grid c2' }, ...Object.values(kinds).map(k => h('button', {
        class: 'pick', onClick: () => location.hash = `#/kp?kind=${k.kind}`,
      }, h('div', { class: 'pico' }, 'ԿՊ' + k.kind),
        h('div', {}, h('div', { class: 'pt', text: k.short }), h('div', { class: 'pd', text: k.subtitle })))))));
    box.append(samples);
    return box;
  }
  const pre = S.prefill?.section === 'kp' ? S.prefill.data : null;
  S.prefill = null;
  return form(kinds[params.kind], L, pre);
}

function form(kind, L, prefill) {
  const data = {};
  const inputs = {};
  const box = h('div');
  const apply = values => {
    let n = 0;
    Object.entries(values || {}).forEach(([k, v]) => { if (setField(inputs[k], Array.isArray(v) ? v.join('\n') : v)) n++; });
    return n;
  };
  const photo = photoButton({
    section: `Commercial offer (КП) type ${kind.kind}: ${kind.short}`, cls: 'btn primary',
    note: 'A request, e-mail, business card or price list from the customer.',
    fields: kind.fields.map(f => ({ key: f.key, label: f.label, hint: f.prompt,
      type: f.input === 'lines' ? 'list' : (f.input === 'number' ? 'number' : 'string') })),
    onResult: res => apply(res.values) });
  box.append(h('div', { class: 'card-head' },
    h('button', { class: 'btn sm ghost', onClick: () => location.hash = '#/kp' }, '← ' + t('btn.back')),
    h('h2', { style: 'margin:0', text: `💼 ${kind.short}` }), h('span', { class: 'badge plain', text: 'ԿՊ ' + kind.kind }),
    h('div', { class: 'right' }, photo)));
  if (prefill) setTimeout(() => { apply(prefill); toast(L ? 'КП открыто в форме: измените и создайте заново' : 'ԿՊ-ն բացվեց ձևում՝ փոխեք և ստեղծեք նորից'); }, 0);

  const grid = h('div', { class: 'grid c2' });
  kind.fields.forEach(f => {
    let input;
    if (f.input === 'lines' || f.input === 'textarea') {
      input = h('textarea', { rows: f.input === 'lines' ? '6' : '3', placeholder: f.placeholder || '' });
      if (f.default) input.value = f.default;
    } else if (f.input === 'number') {
      input = h('input', { type: 'text', inputmode: 'decimal', value: f.default ?? '', placeholder: f.placeholder || '' });
    } else {
      input = h('input', { type: 'text', value: f.default ?? '', placeholder: f.placeholder || '' });
    }
    data[f.key] = input.value;
    input.addEventListener('input', () => { data[f.key] = input.value; });
    inputs[f.key] = input;
    const wrap = field(f.label + (f.optional ? ` (${L ? 'необязательно' : 'ըստ ցանկության'})` : ''), input,
      { hint: f.prompt });
    if (f.input === 'lines') wrap.style.gridColumn = '1 / -1';
    grid.append(wrap);
  });
  box.append(h('div', { class: 'card' }, h('h3', { text: kind.subtitle }), h('div', { class: 'gradline' }), grid));

  const result = h('div');
  const make = h('button', { class: 'btn primary' }, '✅ ' + (L ? 'Создать КП (PDF)' : 'Ստեղծել ԿՊ (PDF)'));
  make.addEventListener('click', async () => {
    Object.values(inputs).forEach(i => i.classList.remove('bad'));
    box.querySelectorAll('.err').forEach(e => e.remove());
    loader(true, L ? 'Готовлю PDF…' : 'PDF-ը պատրաստվում է…');
    try {
      const res = await api('/api/kp/create', { method: 'POST', body: { kind: kind.kind, data }, quiet: true });
      clear(result).append(filesResult(res.files));
      toast(t('msg.ready'));
      S.meta.clients = await api('/api/clients', { quiet: true }).catch(() => S.meta.clients);
      result.scrollIntoView({ behavior: 'smooth' });
    } catch (e) {
      const errors = e.data?.errors;
      if (errors) {
        let first = null;
        Object.entries(errors).forEach(([k, msg]) => {
          const inp = inputs[k];
          if (!inp) return;
          inp.classList.add('bad');
          (inp.closest('.field') || inp.parentElement).append(h('div', { class: 'err', text: msg }));
          if (!first) first = inp;
        });
        toast((L ? 'Проверьте поля: ' : 'Ստուգեք դաշտերը՝ ') + Object.keys(errors).length, 'err');
        if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else toast(e.message, 'err');
    } finally { loader(false); }
  });
  box.append(h('div', { class: 'card' }, h('div', { class: 'row' }, make,
    h('span', { class: 'tiny muted', text: L ? 'Без подписи и печати — как в боте' : 'Առանց ստորագրության և կնիքի՝ ինչպես բոտում' }))));
  box.append(result);
  return box;
}
