"""Minimal same-origin harness for teammates to exercise the backend."""
from html import escape


def render_transcript(room, persona):
    e=lambda value:escape(str(value))
    body=f'<h1>{e(room["topic"])}</h1><p>{e(room["author_label"])} · 状态：{e(room["status"])}</p>'
    body+=f'<p>{e(room.get("test_user","用户与AI观点分身讨论"))}</p><p>作者分身为AI模拟，辩论团成员为虚构AI角色；来源引用存在不代表陈述已被证实。</p>'
    docs={d['id']:d for d in persona['documents']}
    for turn in room['turns']:
        body+=f'<article><h2>{e(turn["name"])}</h2><p>{e(turn["text"])}</p>'
        if turn.get('reply_to_quote'):
            body+=f'<blockquote>回应：{e(turn["reply_to_quote"])}</blockquote>'
        if turn.get('quotes'):
            body+='<details><summary>查看原文依据</summary>'
            for q in turn['quotes']:
                body+=f'<blockquote>{e(q["quote"])}</blockquote>'
                if q['source_id'] in docs:
                    d=docs[q['source_id']]
                    body+=f'<a href="{e(d["url"])}" rel="noreferrer">{e(d.get("title") or "来源")}</a>'
            body+='</details>'
        body+='</article>'
    if room.get('error'):
        body+=f'<p>{e(room["error"])}</p>'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>分身讨论实测记录</title><style>body{max-width:850px;margin:30px auto;padding:20px;font:16px/1.8 system-ui;background:#f5f3ed;color:#19313a}article{background:white;margin:18px 0;padding:18px;border-radius:12px}blockquote{border-left:3px solid #789;padding-left:15px}summary{cursor:pointer}</style>'+body+'</html>'


PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>分身讨论室</title>
<style>body{max-width:850px;margin:30px auto;padding:0 20px;background:#f5f3ed;color:#19313a;font:16px/1.8 system-ui}button,textarea,input{font:inherit}textarea{width:100%;box-sizing:border-box;padding:12px}button{padding:8px 18px;cursor:pointer;background:#245d68;color:white;border:0;border-radius:7px}article{padding:18px;margin:14px 0;background:white;border-radius:12px}blockquote{border-left:3px solid #789;padding-left:12px}#status{color:#53636c}summary{cursor:pointer}</style>
<h1>找个不一样的脑子聊聊</h1><p>与作者公开材料生成的 AI 分身讨论，邀请辩论团从实践和澄清两个角度追问。</p>
<label><input id="council" type="checkbox" checked> 邀请 AI 辩论团</label> <button id="start">新建示例讨论室</button>
<p id="status">示例：解虫的远程协作观点分身。非本人；使用公开文章选摘生成。</p><div id="turns"></div>
<form id="form"><textarea id="message" rows="4" minlength="4" maxlength="1500" required placeholder="说出你的立场，也可以追问上一轮观点">我设想带一个十人软件团队，想把远程设为默认。新人每周来两天，其余人按交付验收。你具体反对哪里？</textarea><button id="send" disabled>发送并讨论</button></form>
<p>引用可以展开核对。辩论团是虚构 AI 角色，不代表真实作者，不评判输赢。</p>
<script>
let roomId=null, busy=false;
const el=id=>document.getElementById(id);
const status=text=>{el('status').textContent=text;};
async function request(path,body){const r=await fetch('/api/v1'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const data=await r.json();if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));return data;}
function render(room){el('turns').replaceChildren();for(const t of room.turns){const card=document.createElement('article'),name=document.createElement('strong'),text=document.createElement('p');name.textContent=t.name;text.textContent=t.text;card.append(name,text);if(t.reply_to_quote){const anchor=document.createElement('blockquote');anchor.textContent='回应：'+t.reply_to_quote;card.append(anchor);}if(t.quotes?.length){const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='查看来源原话';details.append(summary);for(const q of t.quotes){const quote=document.createElement('blockquote');quote.textContent=q.source_id+'：'+q.quote;details.append(quote);}card.append(details);}el('turns').append(card);}status('讨论室 '+room.id+' · '+room.status+(room.error?' · '+room.error:''));}
function controls(value){busy=value;el('send').disabled=value||!roomId;el('start').disabled=value;}
el('start').onclick=async()=>{controls(true);try{const r=await request('/rooms/demo',{council:el('council').checked});roomId=r.id;render(r);const profile=await request('/personas/'+encodeURIComponent(r.persona_id));const card=document.createElement('article');card.textContent=profile.facets.map(f=>f.description).join('；');el('turns').append(card);const link=document.createElement('a');link.href=profile.documents[0].url;link.textContent='查看作者材料来源';link.target='_blank';link.rel='noreferrer';card.append(document.createElement('br'),link);}catch(e){status(e.message);}finally{controls(false);}};
el('form').onsubmit=async event=>{event.preventDefault();if(busy||!roomId)return;const message=el('message').value.trim();if(message.length<4)return;controls(true);status('分身正在回应，随后辩论团发言，可能需要约一分钟…');try{render(await request('/rooms/'+roomId+'/messages',{message}));el('message').value='';}catch(e){status(e.message);try{render(await request('/rooms/'+roomId));}catch{}}finally{controls(false);}};
const existing=new URLSearchParams(location.search).get('room');if(existing){controls(true);request('/rooms/'+encodeURIComponent(existing)).then(room=>{roomId=room.id;render(room);}).catch(e=>status(e.message)).finally(()=>controls(false));}
</script></html>'''
