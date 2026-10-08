// 🎙 Դիկտոր՝ բեռնեք ձայնի MP3 նմուշ -> ուղարկեք տեքստ կամ ձայնային հաղորդագրություն -> ստացեք MP3 դիկտորի ձայնով
import { S, api, clear, confirmDlg, emptyBox, filesResult, h, loader, modal, photoButton, promptDlg, setField, t,
  toast } from '../core.js';

export const sub = () => S.lang === 'ru' ? 'Диктор: ваш голос из MP3 → озвучка текста или голосового сообщения'
  : 'Դիկտոր՝ ձեր ձայնը MP3-ից → տեքստի կամ ձայնային հաղորդագրության ձայնագրում';

let VOICE = '';
let TAB = 'text';
let MODE = 'convert';
const REC_OK = !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);

/* ---- խոսափողից ձայնագրություն (աշխատում է localhost-ում և https-ով) ---- */
function recorder(L, onDone) {
  const btn = h('button', { class: 'btn rec' }, '🔴 ' + (L ? 'Записать' : 'Ձայնագրել'));
  const timer = h('span', { class: 'tiny muted', text: '' });
  let rec = null, chunks = [], t0 = 0, tick = null, stream = null;
  const stop = () => { if (rec && rec.state !== 'inactive') rec.stop(); };
  btn.addEventListener('click', async () => {
    if (rec && rec.state === 'recording') { stop(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      toast(L ? 'Нет доступа к микрофону. Разрешите его в браузере.' : 'Խոսափողի հասանելիություն չկա: Թույլատրեք բրաուզերում:', 'err');
      return;
    }
    chunks = [];
    rec = new MediaRecorder(stream);
    rec.ondataavailable = ev => { if (ev.data.size) chunks.push(ev.data); };
    rec.onstop = () => {
      clearInterval(tick); stream.getTracks().forEach(tr => tr.stop());
      btn.textContent = '🔴 ' + (L ? 'Записать' : 'Ձայնագրել'); btn.classList.remove('on');
      const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
      const ext = (rec.mimeType || '').includes('ogg') ? 'ogg' : (rec.mimeType || '').includes('mp4') ? 'mp4' : 'webm';
      onDone(new File([blob], `record.${ext}`, { type: blob.type }), (Date.now() - t0) / 1000);
    };
    rec.start();
    t0 = Date.now();
    btn.textContent = '⏹ ' + (L ? 'Стоп' : 'Կանգնեցնել'); btn.classList.add('on');
    tick = setInterval(() => { timer.textContent = `${Math.floor((Date.now() - t0) / 1000)} ${L ? 'сек' : 'վրկ'}`; }, 300);
  });
  return h('span', { class: 'inline', style: 'gap:8px;width:auto' }, btn, timer);
}

export async function render() {
  const L = S.lang === 'ru' ? 1 : 0;
  const root = h('div');
  const voicesBox = h('div');
  const studio = h('div');
  const result = h('div');
  let msgFile = null;           // ձայնային հաղորդագրություն (բեռնված կամ ձայնագրված)

  // ------------------------------------------------ կարգավիճակ (կլոնի գրադարաններ)
  const status = await api('/api/voice/status', { quiet: true }).catch(() => null);
  if (status && !status.clone_ready) {
    root.append(h('div', { class: 'card', style: 'border-color:var(--warn)' },
      h('h3', { text: '⚠️ ' + (L ? 'Диктор ещё не установлен' : 'Դիկտորը դեռ տեղադրված չէ') }),
      h('p', { class: 'small', text: L
        ? `Для клонирования голоса нужны библиотеки (${status.missing.join(', ')}). Закройте приложение, запустите install_voice.bat (один раз, несколько минут), затем снова run.bat.`
        : `Ձայնի կլոնավորման համար պետք են գրադարաններ (${status.missing.join(', ')}): Փակեք հավելվածը, գործարկեք install_voice.bat (մեկ անգամ, մի քանի րոպե), հետո նորից run.bat:` })));
  }

  // ------------------------------------------------ 1. դիկտորներ
  async function loadVoices() {
    clear(voicesBox);
    let voices = [];
    try { voices = await api('/api/voice/voices'); } catch (e) {
      voicesBox.append(h('p', { class: 'small', style: 'color:var(--warn)', text: e.message })); return;
    }
    if (!VOICE || !voices.some(v => v.key === VOICE)) VOICE = (voices.find(v => v.kind === 'clone') || voices[0] || {}).key || '';
    if (!voices.length) { voicesBox.append(emptyBox(L ? 'Голосов нет' : 'Ձայներ չկան', '🎙')); return; }
    const grid = h('div', { class: 'grid c3' });
    voices.forEach(v => {
      const clone = v.kind === 'clone';
      const pick = h('button', { class: 'pick' + (VOICE === v.key ? ' sel' : '') },
        h('div', { class: 'pico' }, clone ? '🧬' : '🔊'),
        h('div', { style: 'flex:1' }, h('div', { class: 'pt', text: v.name }),
          h('div', { class: 'pd', text: clone ? (L ? 'диктор · ваш голос' : 'դիկտոր · ձեր ձայնը')
            : (L ? 'готовый голос (только текст)' : 'պատրաստի ձայն (միայն տեքստ)') })));
      pick.addEventListener('click', () => { VOICE = v.key; loadVoices(); drawStudio(); });
      const tools = h('div', { class: 'row tight', style: 'margin-top:8px' },
        h('button', { class: 'btn sm', onClick: async () => {
          loader(true, L ? 'Готовлю образец…' : 'Նմուշը պատրաստվում է…');
          try {
            const r = await api('/api/voice/sample', { method: 'POST', body: { key: v.key } });
            modal({ title: '🔊 ' + v.name, body: player(r.files[0]) });
          } catch (e) { /* toast */ } finally { loader(false); }
        } }, '▶ ' + (L ? 'Образец' : 'Նմուշ')),
        clone ? h('button', { class: 'btn sm danger', onClick: async () => {
          if (!await confirmDlg(L ? `Удалить голос «${v.name}»?` : `Ջնջե՞լ «${v.name}» ձայնը:`)) return;
          await api(`/api/voice/${v.key}`, { method: 'DELETE' });
          if (VOICE === v.key) VOICE = '';
          toast(t('msg.deleted')); loadVoices(); drawStudio();
        } }, '🗑') : null);
      grid.append(h('div', {}, pick, tools));
    });
    voicesBox.append(grid);
  }

  async function addVoice(file) {
    const name = await promptDlg(L ? 'Имя диктора' : 'Դիկտորի անունը',
      { placeholder: L ? 'например: Арам' : 'օրինակ՝ Արամ' });
    if (!name) return;
    const fd = new FormData(); fd.append('name', name); fd.append('file', file);
    loader(true, L ? 'Проверяю запись…' : 'Ստուգում եմ ձայնագրությունը…');
    try {
      const r = await api('/api/voice/upload', { method: 'POST', form: fd });
      toast(`✅ ${name} · ${r.seconds} ${L ? 'сек' : 'վրկ'}` + (r.warning ? `\n⚠️ ${r.warning}` : ''), r.warning ? 'warn' : 'ok');
      VOICE = r.key;
      await loadVoices(); drawStudio();
    } catch (e) { /* toast */ } finally { loader(false); }
  }
  const upl = h('input', { type: 'file', accept: 'audio/*', style: 'display:none' });
  upl.addEventListener('change', () => { if (upl.files.length) addVoice(upl.files[0]); upl.value = ''; });

  root.append(h('div', { class: 'card' },
    h('div', { class: 'card-head' },
      h('h2', { style: 'margin:0', text: '🎙 ' + (L ? '1. Диктор' : '1. Դիկտոր') }),
      h('div', { class: 'right' },
        REC_OK ? recorder(L, (f, sec) => { if (sec < 3) toast(L ? 'Слишком коротко (нужно от 3 сек, лучше 1–3 минуты)' : 'Շատ կարճ է (պետք է 3 վրկ-ից, լավ է՝ 1–3 րոպե)', 'err'); else addVoice(f); }) : null,
        h('button', { class: 'btn primary', onClick: () => upl.click() }, '⬆️ ' + (L ? 'Добавить MP3 голоса' : 'Ավելացնել ձայնի MP3')), upl)),
    h('p', { class: 'small muted', text: L
      ? 'Загрузите MP3 с голосом человека (1–3 минуты чистой речи, без музыки) — он станет диктором. Дальше выберите диктора и отправьте текст или голосовое сообщение.'
      : 'Բեռնեք մարդու ձայնով MP3 (1–3 րոպե մաքուր խոսք՝ առանց երաժշտության)՝ նա կդառնա դիկտոր: Հետո ընտրեք դիկտորին և ուղարկեք տեքստ կամ ձայնային հաղորդագրություն:' }),
    voicesBox));

  // ------------------------------------------------ 2. ստուդիա
  const text = h('textarea', { rows: '6', placeholder: L ? 'Текст для озвучки (на армянском)…' : 'Տեքստը ձայնագրելու համար (հայերեն)…' });
  const count = h('span', { class: 'tiny muted', text: '0' });
  text.addEventListener('input', () => { count.textContent = String(text.value.length); });
  const fileName = h('div', { class: 'small', style: 'margin-top:8px' });
  const msgInput = h('input', { type: 'file', accept: 'audio/*,video/mp4,video/webm', style: 'display:none' });
  const setMsg = (f, sec) => {
    msgFile = f;
    fileName.textContent = `🎧 ${f.name}` + (sec ? ` · ${Math.round(sec)} ${L ? 'сек' : 'վրկ'}` : '');
    clear(preview).append(h('audio', { controls: true, src: URL.createObjectURL(f), style: 'width:100%;margin-top:8px' }));
  };
  const preview = h('div');
  msgInput.addEventListener('change', () => { if (msgInput.files.length) setMsg(msgInput.files[0]); msgInput.value = ''; });

  function drawStudio() {
    clear(studio);
    const cur = VOICE;
    const tabs = h('div', { class: 'seg', style: 'margin-bottom:14px' },
      h('button', { class: TAB === 'text' ? 'on' : '', onClick: () => { TAB = 'text'; drawStudio(); } }, '✍️ ' + (L ? 'Текст' : 'Տեքստ')),
      h('button', { class: TAB === 'voice' ? 'on' : '', onClick: () => { TAB = 'voice'; drawStudio(); } }, '🎤 ' + (L ? 'Голосовое сообщение' : 'Ձայնային հաղորդագրություն')));
    const go = h('button', { class: 'btn primary lg' }, '🎙 ' + (L ? 'Озвучить диктором' : 'Ձայնագրել դիկտորով'));
    go.addEventListener('click', run);
    let body;
    if (TAB === 'text') {
      const photo = photoButton({ section: 'Text for a voice-over (radio/in-store audio ad script)', cls: 'btn sm',
        fields: [{ key: 'text', type: 'text', label: 'The full text to be read aloud, exactly as written (keep the language)' }],
        onResult: res => setField(text, res.values?.text) });
      body = h('div', {}, h('div', { class: 'row', style: 'justify-content:space-between;margin-bottom:6px' },
        h('span', { class: 'small muted', text: L ? 'Что должен сказать диктор' : 'Ինչ պետք է ասի դիկտորը' }),
        h('div', { class: 'row tight' }, photo, count)), text);
    } else {
      const zone = h('div', { class: 'dropzone' }, h('div', { class: 'dzi' }, '🎤'),
        h('div', { text: L ? 'Нажмите или перетащите голосовое сообщение (mp3, ogg, wav, m4a, webm)' : 'Սեղմեք կամ քաշեք ձայնային հաղորդագրությունը (mp3, ogg, wav, m4a, webm)' }));
      zone.addEventListener('click', () => msgInput.click());
      zone.addEventListener('dragover', ev => { ev.preventDefault(); zone.classList.add('over'); });
      zone.addEventListener('dragleave', () => zone.classList.remove('over'));
      zone.addEventListener('drop', ev => { ev.preventDefault(); zone.classList.remove('over'); if (ev.dataTransfer.files.length) setMsg(ev.dataTransfer.files[0]); });
      const modes = h('div', { class: 'grid c2', style: 'margin-top:12px' },
        ...[['convert', '🧬', L ? 'Голос → голос диктора' : 'Ձայն → դիկտորի ձայն', L ? 'Сохраняет интонацию и темп. Текст не распознаётся.' : 'Պահպանում է ինտոնացիան և տեմպը: Տեքստը չի ճանաչվում:'],
          ['retell', '📝', L ? 'Распознать и прочитать' : 'Ճանաչել և կարդալ', L ? 'Речь → текст → диктор читает заново (чище дикция).' : 'Խոսք → տեքստ → դիկտորը կարդում է նորից (մաքուր արտասանություն):']]
          .map(([id, ic, tt, dd]) => h('button', { class: 'pick' + (MODE === id ? ' sel' : ''), onClick: () => { MODE = id; drawStudio(); } },
            h('div', { class: 'pico' }, ic), h('div', {}, h('div', { class: 'pt', text: tt }), h('div', { class: 'pd', text: dd })))));
      body = h('div', {}, zone, msgInput,
        REC_OK ? h('div', { class: 'row', style: 'margin-top:10px' }, recorder(L, (f, sec) => setMsg(f, sec)),
          h('span', { class: 'tiny muted', text: L ? 'или запишите голосовое прямо здесь' : 'կամ ձայնագրեք հենց այստեղ' }))
          : h('p', { class: 'tiny muted', style: 'margin-top:8px', text: L ? 'Запись с микрофона работает на этом компьютере (localhost) или по https. Загрузите готовый файл.' : 'Խոսափողից ձայնագրությունը աշխատում է այս համակարգչում (localhost) կամ https-ով: Բեռնեք պատրաստի ֆայլ:' }),
        fileName, preview, modes);
    }
    const who = h('div', { class: 'small muted', style: 'margin-bottom:10px' });
    api('/api/voice/voices', { quiet: true }).then(vs => {
      const v = vs.find(x => x.key === cur);
      who.textContent = v ? `${L ? 'Диктор' : 'Դիկտոր'}: ${v.name}` : (L ? 'Выберите диктора выше' : 'Ընտրեք դիկտորին վերևում');
    }).catch(() => {});
    studio.append(h('div', { class: 'card' },
      h('h2', { text: '✨ ' + (L ? '2. Что озвучить' : '2. Ինչ ձայնագրել') }), who, tabs, body,
      h('div', { class: 'row', style: 'margin-top:14px' }, go)));
  }

  async function run() {
    if (!VOICE) { toast(L ? 'Сначала выберите диктора' : 'Նախ ընտրեք դիկտորին', 'err'); return; }
    try {
      loader(true, L ? 'Диктор работает… (первый раз до нескольких минут)' : 'Դիկտորը աշխատում է… (առաջին անգամ՝ մի քանի րոպե)');
      let r;
      if (TAB === 'text') {
        if (!text.value.trim()) { toast(L ? 'Введите текст' : 'Մուտքագրեք տեքստը', 'err'); return; }
        r = await api('/api/voice/synth', { method: 'POST', body: { key: VOICE, text: text.value } });
      } else {
        if (!msgFile) { toast(L ? 'Добавьте голосовое сообщение' : 'Ավելացրեք ձայնային հաղորդագրություն', 'err'); return; }
        const fd = new FormData(); fd.append('file', msgFile); fd.append('key', VOICE); fd.append('mode', MODE);
        r = await api('/api/voice/dub', { method: 'POST', form: fd });
      }
      clear(result).append(h('div', { class: 'card' },
        h('h2', { text: '✅ ' + (L ? 'Готово' : 'Պատրաստ է') }),
        r.text ? h('p', { class: 'small', text: (L ? 'Распознанный текст: ' : 'Ճանաչված տեքստ՝ ') + r.text }) : null,
        player(r.files[0]), filesResult(r.files)));
      result.scrollIntoView({ behavior: 'smooth' });
    } catch (e) { /* toast-ը ցույց է տրվել */ } finally { loader(false); }
  }

  root.append(studio, result);
  await loadVoices();
  drawStudio();
  return root;
}

function player(file) {
  return h('div', { style: 'margin:0 0 10px' },
    h('audio', { controls: true, src: file.url, style: 'width:100%' }),
    h('div', { class: 'tiny muted', text: file.name }));
}
