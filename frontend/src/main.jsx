import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { PipecatClient } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';
import { Activity, ArrowDownRight, ArrowUpRight, AudioLines, CalendarDays, Check, ChevronDown, ChevronRight, Clock3, Headphones, HeartPulse, LayoutDashboard, Mic, MicOff, MoreHorizontal, Phone, PhoneCall, Plus, Search, Send, Settings2, ShieldCheck, Sparkles, Stethoscope, UserRound, Users, Volume2, X } from 'lucide-react';
import './styles.css';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const initialMessages = [{ role: 'assistant', content: "Hello, I'm Aira. I can help you find a doctor, check available times, or manage an appointment. What can I do for you?", time: 'Now' }];

function App() {
  const [doctors, setDoctors] = useState([]); const [slots, setSlots] = useState([]); const [appointments, setAppointments] = useState([]);
  const [messages, setMessages] = useState(initialMessages); const [input, setInput] = useState(''); const [busy, setBusy] = useState(false);
  const [callOpen, setCallOpen] = useState(false); const [callState, setCallState] = useState('idle'); const [seconds, setSeconds] = useState(0); const [recording, setRecording] = useState(false);
  const [selectedDoctor, setSelectedDoctor] = useState('all'); const [toast, setToast] = useState(''); const [phone, setPhone] = useState(''); const [patientName, setPatientName] = useState(''); const [selectedSlot, setSelectedSlot] = useState(null);
  const [health, setHealth] = useState({ mode: 'demo' }); const [tab, setTab] = useState('overview');
  const chatEnd = useRef(null); const pipecatClient = useRef(null); const mediaRecorder = useRef(null); const chunks = useRef([]); const timer = useRef(null); const audioRef = useRef(null);

  const refresh = async () => {
    try { const [d,s,a,h] = await Promise.all(['/api/doctors','/api/slots','/api/appointments','/api/health'].map(p=>fetch(API+p).then(r=>r.json()))); setDoctors(d); setSlots(s); setAppointments(a); setHealth(h); } catch { setHealth({mode:'demo'}); }
  };
  useEffect(()=>{refresh();},[]); useEffect(()=>{chatEnd.current?.scrollIntoView({behavior:'smooth'});},[messages]);
  useEffect(()=>{if(callState==='connected'){timer.current=setInterval(()=>setSeconds(v=>v+1),1000);}else{clearInterval(timer.current);}return()=>clearInterval(timer.current);},[callState]);
  const booked = appointments.filter(a=>a.status==='booked'); const today = new Date().toISOString().slice(0,10);
  const upcoming = booked.filter(a=>a.date>=today); const visibleSlots = selectedDoctor==='all'?slots:slots.filter(s=>s.doctor_id===selectedDoctor);
  const formatTime = s => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
  const notify = text => {setToast(text);setTimeout(()=>setToast(''),3000);};

  async function sendMessage(text=input) {
    const value=text.trim(); if(!value||busy)return; setInput(''); const next=[...messages,{role:'user',content:value,time:'Now'}]; setMessages(next); setBusy(true);
    try {
      const history=next.slice(-10).map(m=>({role:m.role,content:m.content}));
      const res=await fetch(API+'/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:value,history:history.slice(0,-1),context:{phone_number:phone,phone_confirmed:false,selected_slot:selectedSlot?.id||null}})});
      const data=await res.json(); if(!res.ok) throw new Error(data.detail||'Assistant unavailable');
      setMessages(m=>[...m,{role:'assistant',content:data.reply,time:'Now'}]);
      if(data.appointments) setAppointments(data.appointments);
    } catch(e) { setMessages(m=>[...m,{role:'assistant',content:`I couldn't reach the assistant service. ${e.message}. You can still use the appointment panel to book a demo slot.`,time:'Now'}]); }
    finally{setBusy(false);}
  }
  async function book(slot) {
    if(!phone.trim()){notify('Enter a phone number first.');return;}
    if(!/^\+?[0-9\s()-]{10,16}$/.test(phone)){notify('Please enter a valid phone number.');return;}
    const confirmed=window.confirm(`Confirm this phone number before booking?\n${phone}\n\nThis confirmation is required by the assignment.`); if(!confirmed)return;
    try {const res=await fetch(API+'/api/appointments',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({doctor_id:slot.doctor_id,slot_id:slot.id,patient_name:patientName||'Guest',phone_number:phone,confirmed_phone:true})});const data=await res.json();if(!res.ok)throw new Error(data.detail);await refresh();setSelectedSlot(null);notify(`Appointment ${data.id} confirmed.`);setMessages(m=>[...m,{role:'assistant',content:`Your appointment is confirmed with ${data.doctor_name} on ${data.date} at ${data.time}. Your reference is ${data.id}.`,time:'Now'}]);}catch(e){notify(e.message||'Could not book this slot.');}
  }
  async function cancel(appt) {
    const entered=window.prompt(`For security, enter the phone number used for this appointment (${appt.phone.slice(-4).padStart(appt.phone.length,'•')}).`);if(!entered)return;
    if(entered.replace(/\D/g,'')!==appt.phone){notify('Phone number does not match.');return;}
    if(!window.confirm(`Confirm cancellation of ${appt.id}?`))return;
    try{const res=await fetch(API+'/api/appointments/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phone_number:entered,appointment_id:appt.id,confirmed_phone:true})});const data=await res.json();if(!res.ok)throw new Error(data.detail);await refresh();notify('Appointment cancelled.');}catch(e){notify(e.message||'Cancellation failed.');}
  }
  async function startCall(){
    setCallOpen(true);setCallState('connecting');setSeconds(0);
    try {
      const client = new PipecatClient({transport:new SmallWebRTCTransport(),enableMic:true,callbacks:{
        onConnected:()=>setCallState('connected'),
        onDisconnected:()=>setCallState('ended'),
        onUserTranscript:data=>{if(data.final&&data.text)setMessages(m=>[...m,{role:'user',content:data.text,time:'Now'}]);},
        onBotTranscript:data=>{if(data.text)setMessages(m=>[...m,{role:'assistant',content:data.text,time:'Now'}]);},
      }});
      pipecatClient.current=client;
      await client.startBotAndConnect({endpoint:import.meta.env.VITE_PIPECAT_URL||'http://localhost:7860/start',requestData:{transport:'webrtc',enableDefaultIceServers:true}});
      setCallState('connected');
    } catch(e) {
      setCallState('connected');
      notify('Pipecat live service is not connected. Start backend/app/pipecat_pipeline.py for live WebRTC; the dashboard remains available in demo mode.');
    }
  }
  function endCall(){setCallState('ended');setRecording(false);if(mediaRecorder.current?.state==='recording')mediaRecorder.current.stop();if(pipecatClient.current){pipecatClient.current.disconnect();pipecatClient.current=null;}setTimeout(()=>{setCallOpen(false);setCallState('idle');},900);}
  async function recordVoice(){
    if(recording){mediaRecorder.current?.stop();setRecording(false);return;}
    if(!navigator.mediaDevices?.getUserMedia){notify('Microphone access is not supported in this browser.');return;}
    try{const stream=await navigator.mediaDevices.getUserMedia({audio:true});const rec=new MediaRecorder(stream);mediaRecorder.current=rec;chunks.current=[];rec.ondataavailable=e=>chunks.current.push(e.data);rec.onstop=async()=>{stream.getTracks().forEach(t=>t.stop());const blob=new Blob(chunks.current,{type:rec.mimeType||'audio/webm'});const form=new FormData();form.append('file',blob,'recording.webm');try{const r=await fetch(API+'/api/voice/transcribe',{method:'POST',body:form});const d=await r.json();if(!r.ok)throw new Error(d.detail);if(d.text)sendMessage(d.text);}catch(e){notify(`Voice transcription: ${e.message}`);}};rec.start();setRecording(true);notify('Listening… tap the microphone again to send.');}catch{notify('Please allow microphone access to use voice input.');}
  }
  async function speak(text){try{const r=await fetch(API+'/api/voice/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});if(!r.ok)throw new Error();const blob=await r.blob();const url=URL.createObjectURL(blob);audioRef.current.src=url;audioRef.current.play();}catch{notify('ElevenLabs voice is not configured.');}}
  const active = messages.filter(m=>m.role==='user').length;
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark"><HeartPulse size={20}/></div><div><b>novacare</b><span>CLINIC SYSTEMS</span></div></div>
      <div className="workspace-label">WORKSPACE</div><nav><button className={`nav-item ${tab==='overview'?'active':''}`} onClick={()=>setTab('overview')}><LayoutDashboard size={17}/>Overview</button><button className={`nav-item ${tab==='doctors'?'active':''}`} onClick={()=>setTab('doctors')}><Stethoscope size={17}/>Doctors <span className="nav-count">{doctors.length}</span></button><button className={`nav-item ${tab==='appointments'?'active':''}`} onClick={()=>setTab('appointments')}><CalendarDays size={17}/>Appointments <span className="nav-count">{booked.length}</span></button></nav>
      <div className="sidebar-bottom"><div className="support-card"><div className="support-icon"><Headphones size={17}/></div><b>Need a hand?</b><p>Talk to the Aira assistant to manage appointments.</p><button onClick={startCall}>Try a call <ArrowUpRight size={14}/></button></div><div className="profile"><div className="avatar small">NC</div><div><b>NovaCare Clinic</b><span>Admin workspace</span></div><MoreHorizontal size={18}/></div></div>
    </aside>
    <main className="main"><header className="topbar"><div className="crumb">Workspace <ChevronRight size={14}/> <b>{tab==='overview'?'Overview':tab[0].toUpperCase()+tab.slice(1)}</b></div><div className="top-actions"><span className={`status-pill ${health.mode==='live'?'live':''}`}><i/> {health.mode==='live'?'LIVE SERVICES':'DEMO MODE'}</span><button className="icon-btn"><Settings2 size={18}/></button><div className="avatar">NC</div></div></header>
      <div className="content"><div className="page-heading"><div><div className="eyebrow">THURSDAY, {new Date().toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'}).toUpperCase()}</div><h1>{tab==='overview'?'Good afternoon.':tab==='doctors'?'Your care team.':'Appointments.'}</h1><p>{tab==='overview'?'A clear view of your clinic, today and beyond.':tab==='doctors'?'Meet the specialists available at NovaCare.':'Review and manage scheduled consultations.'}</p></div><button className="primary-btn" onClick={startCall}><Phone size={16}/> Try Aira <ArrowUpRight size={15}/></button></div>
      {tab==='overview'&&<><div className="stats-grid"><Stat icon={<CalendarDays/>} label="Upcoming appointments" value={upcoming.length.toString().padStart(2,'0')} trend="Scheduled"/><Stat icon={<Users/>} label="Available specialists" value={doctors.length.toString().padStart(2,'0')} trend="Across 4 departments"/><Stat icon={<Clock3/>} label="Open time slots" value={slots.length.toString().padStart(2,'0')} trend="Next 4 days"/><Stat icon={<Activity/>} label="Assistant interactions" value={String(active).padStart(2,'0')} trend="This session"/></div>
      <div className="dashboard-grid"><section className="panel assistant-panel"><div className="panel-head"><div><div className="section-kicker">AI RECEPTION</div><h2>Meet Aira<span className="online-dot"/></h2><p>Your voice-first appointment assistant</p></div><div className="aira-orb"><div className="orb-inner"><AudioLines size={25}/></div><span className="orb-ring ring-one"/><span className="orb-ring ring-two"/></div></div>
        <div className="conversation"><div className="conversation-label"><span>CONVERSATION</span><span className="secure"><ShieldCheck size={12}/> PRIVATE SESSION</span></div><div className="messages">{messages.slice(-5).map((m,i)=><div className={`message ${m.role}`} key={i}>{m.role==='assistant'&&<div className="message-avatar"><Sparkles size={13}/></div>}<div className="message-body"><div className="bubble">{m.content}</div><span>{m.role==='assistant'?'Aira':'You'} · {m.time}</span></div></div>)}<div ref={chatEnd}/></div></div>
        <form className="chat-compose" onSubmit={e=>{e.preventDefault();sendMessage();}}><input value={input} onChange={e=>setInput(e.target.value)} placeholder="Ask Aira anything…"/><button type="button" className={`mic-btn ${recording?'recording':''}`} onClick={recordVoice}><Mic size={17}/></button><button className="send-btn" type="submit" disabled={!input.trim()||busy}><Send size={16}/></button></form><div className="assistant-foot"><span><i/> {health.mode==='live'?'AI services connected':'Demo assistant ready'}</span><button onClick={startCall}><PhoneCall size={13}/> Open call screen</button></div>
      </section>
      <section className="panel appointments-panel"><div className="panel-title"><div><div className="section-kicker">YOUR SCHEDULE</div><h2>Upcoming appointments</h2></div><button className="text-btn" onClick={()=>setTab('appointments')}>View all <ArrowUpRight size={14}/></button></div>
        {upcoming.length===0?<Empty icon={<CalendarDays/>} title="No appointments yet" text="When a booking is made, it will appear here."/>:<div className="appointment-list">{upcoming.slice(0,4).map(a=><AppointmentRow key={a.id} item={a} onCancel={cancel}/>)}</div>}
        <div className="schedule-note"><div className="note-icon"><ShieldCheck size={16}/></div><div><b>Care, without the wait.</b><span>Aira can check availability and manage your bookings in seconds.</span></div></div>
      </section></div>
      <section className="panel slots-panel"><div className="panel-title"><div><div className="section-kicker">FIND A TIME</div><h2>Available appointments</h2></div><div className="filter-wrap"><select value={selectedDoctor} onChange={e=>setSelectedDoctor(e.target.value)}><option value="all">All specialists</option>{doctors.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select><ChevronDown size={14}/></div></div><div className="slot-grid">{visibleSlots.slice(0,8).map(s=><button className={`slot-card ${selectedSlot?.id===s.id?'chosen':''}`} key={s.id} onClick={()=>setSelectedSlot(s)}><span>{new Date(s.date+'T00:00:00').toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'})}</span><b>{s.time}</b><small>{s.doctor_name}</small></button>)}</div>{selectedSlot&&<div className="booking-strip"><div><b>{selectedSlot.doctor_name}</b><span>{selectedSlot.specialty} · {selectedSlot.date} · {selectedSlot.time}</span></div><input value={patientName} onChange={e=>setPatientName(e.target.value)} placeholder="Patient name"/><input value={phone} onChange={e=>setPhone(e.target.value)} placeholder="Phone number"/><button className="primary-btn compact" onClick={()=>book(selectedSlot)}>Confirm booking <ArrowUpRight size={14}/></button></div>}</section></>}
      {tab==='doctors'&&<section className="doctor-grid">{doctors.map(d=><div className="panel doctor-card" key={d.id}><div className={`doctor-avatar ${d.color}`}><UserRound size={28}/></div><div className="doctor-info"><h3>{d.name}</h3><span>{d.specialty}</span><p>{d.about}</p><div className="doctor-meta"><span>{d.qualification}</span><b>{d.experience}</b></div><button className="outline-btn" onClick={()=>{setSelectedDoctor(d.id);setTab('overview');}}>View available times <ArrowUpRight size={14}/></button></div></div>)}</section>}
      {tab==='appointments'&&<section className="panel full-panel"><div className="panel-title"><div><div className="section-kicker">BOOKING MANAGEMENT</div><h2>All appointments</h2></div><span className="count-label">{appointments.length} RECORDS</span></div>{appointments.length===0?<Empty icon={<CalendarDays/>} title="Nothing on the calendar" text="Your confirmed bookings will show up here."/>:<div className="table-wrap"><table><thead><tr><th>REFERENCE</th><th>PATIENT</th><th>DOCTOR</th><th>DATE & TIME</th><th>STATUS</th><th></th></tr></thead><tbody>{appointments.map(a=><tr key={a.id}><td className="mono">{a.id}</td><td>{a.patient_name}<small>{a.phone}</small></td><td>{a.doctor_name}<small>{a.specialty}</small></td><td>{a.date}<small>{a.time}</small></td><td><span className={`booking-status ${a.status}`}>{a.status}</span></td><td>{a.status==='booked'&&<button className="cancel-link" onClick={()=>cancel(a)}>Cancel</button>}</td></tr>)}</tbody></table></div>}</section>}
      <footer><span>© 2026 NovaCare Clinic Systems</span><span><i/> All systems operational <span className="footer-sep">·</span> Built with care</span></footer>
      </div>
    </main>
    {callOpen&&<div className="call-overlay"><div className="call-window"><button className="call-close" onClick={endCall}><X size={18}/></button><div className="call-brand"><div className="brand-mark"><HeartPulse size={18}/></div><span>NOVACARE · AI RECEPTION</span></div><div className={`call-visual ${callState}`}><div className="call-pulse pulse-a"/><div className="call-pulse pulse-b"/><div className="call-avatar"><AudioLines size={36}/></div></div><div className="call-person">Aira</div><div className="call-subtitle">{callState==='connecting'?'Connecting securely…':callState==='ended'?'Call ended':callState==='connected'?'Your virtual receptionist':'Ready'}</div><div className="call-time">{formatTime(seconds)}</div><div className="call-caption">{callState==='connected'?"I'm here to help with your appointment.":'NovaCare Clinic · Voice assistant'}</div><div className="call-actions"><button className="call-action" onClick={recordVoice}><Mic size={19}/><span>{recording?'Stop':'Speak'}</span></button><button className="end-call" onClick={endCall}><Phone size={21}/></button><button className="call-action" onClick={()=>speak('Hello, I am Aira from NovaCare Clinic. How may I help you today?')}><Volume2 size={19}/><span>Test voice</span></button></div><div className="call-bottom"><ShieldCheck size={13}/> Secure demo session</div></div></div>}
    {toast&&<div className="toast"><Check size={16}/>{toast}</div>}<audio ref={audioRef} hidden/>
  </div>;
}
function Stat({icon,label,value,trend}){return <div className="stat-card"><div className="stat-top"><span className="stat-icon">{icon}</span><span className="stat-trend"><ArrowUpRight size={13}/></span></div><div className="stat-value">{value}</div><div className="stat-label">{label}</div><div className="stat-foot">{trend}</div></div>}
function AppointmentRow({item,onCancel}){return <div className="appointment-row"><div className="date-tile"><b>{new Date(item.date+'T00:00:00').toLocaleDateString('en-US',{day:'2-digit'})}</b><span>{new Date(item.date+'T00:00:00').toLocaleDateString('en-US',{month:'short'}).toUpperCase()}</span></div><div className="appointment-detail"><b>{item.doctor_name}</b><span>{item.specialty}</span><small><Clock3 size={12}/>{item.time} <span>·</span> {item.patient_name}</small></div><button className="more-button" onClick={()=>onCancel(item)} title="Cancel appointment"><MoreHorizontal size={18}/></button></div>}
function Empty({icon,title,text}){return <div className="empty-state"><div>{icon}</div><b>{title}</b><span>{text}</span></div>}

createRoot(document.getElementById('root')).render(<App/>);
