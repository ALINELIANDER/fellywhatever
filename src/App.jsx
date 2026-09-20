import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Cast,
  BookOpen,
  Layers,
  AlertTriangle,
  FileText,
  Library,
  Circle,
  Square,
  RotateCcw,
  Check,
  X,
  Upload,
  Download,
  Plus,
  Play,
  Volume2,
  Image as ImageIcon,
  User,
  LogOut,
} from "lucide-react";
import { latestVisualAidMatch } from "./utils/visualAidMatch";

/* ---------------------------------------------------------------
   Design tokens
---------------------------------------------------------------- */
const COLOR = {
  paper: "#F5F0E3",
  paperDim: "#EDE6D3",
  ink: "#2A2A28",
  inkSoft: "#5C594E",
  indigo: "#1C2B45",
  indigoSoft: "#2E4267",
  ochre: "#C1852E",
  ochreSoft: "#E7C793",
  teal: "#1F6F63",
  tealSoft: "#CFE6E1",
  maroon: "#8C3B33",
  maroonSoft: "#EBD3CF",
  line: "#D8CFB6",
};

const FONT_HEAD = "'IBM Plex Serif', Georgia, serif";
const FONT_BODY = "'IBM Plex Sans', 'Segoe UI', sans-serif";

const FontImport = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
    * { box-sizing: border-box; }
    .flip-card { perspective: 1200px; }
    .flip-inner {
      position: relative;
      width: 100%;
      height: 100%;
      transition: transform 0.5s cubic-bezier(.4,.2,.2,1);
      transform-style: preserve-3d;
    }
    .flip-inner.flipped { transform: rotateY(180deg); }
    .flip-face {
      position: absolute;
      inset: 0;
      backface-visibility: hidden;
      -webkit-backface-visibility: hidden;
    }
    .flip-back { transform: rotateY(180deg); }
    .pulse-dot {
      animation: pulse 1.4s infinite;
    }
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.35; }
      100% { opacity: 1; }
    }
    .caption-enter {
      animation: slideIn 0.35s ease-out;
    }
    @keyframes slideIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-thumb { background: ${COLOR.line}; border-radius: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
  `}</style>
);

/* ---------------------------------------------------------------
   Mock data
---------------------------------------------------------------- */
const NAV_ITEMS = [
  { key: "classroom", label: "Live Classroom", icon: Cast },
  { key: "content", label: "Content Library", icon: BookOpen },
  { key: "flashcards", label: "Flashcards", icon: Layers },
  { key: "misconceptions", label: "Misconceptions", icon: AlertTriangle },
  { key: "worksheets", label: "Worksheets", icon: FileText },
  { key: "dictionary", label: "Dictionary", icon: Library },
];

const SCRIPT = [
  { hi: "आज हम देखेंगे कि पौधे अपना भोजन खुद कैसे बनाते हैं।", sat: "ᱛᱮᱦᱮᱸ ᱟᱞᱮ ᱧᱮᱞ ᱟᱠᱟᱱᱟ ᱚᱠᱟ ᱞᱮᱠᱟᱛᱮ ᱵᱟᱦᱟ ᱡᱟᱸᱦᱟᱸ ᱟᱡᱽ ᱡᱚᱢ ᱮᱢ ᱛᱮᱭᱟᱨ ᱠᱚᱨᱚᱣᱟᱭ ᱾", keyword: "photosynthesis" },
  { hi: "इस प्रक्रिया को प्रकाश-संश्लेषण कहते हैं।", sat: "ᱱᱚᱶᱟ ᱠᱟᱹᱢᱤ ᱵᱟᱵᱚᱛ ᱯᱷᱚᱴᱚᱥᱤᱸᱛᱷᱮᱥᱤᱥ ᱢᱮᱱ ᱠᱟᱱᱟ ᱾", keyword: "photosynthesis" },
  { hi: "पत्तियाँ सूर्य के प्रकाश, पानी और कार्बन डाइऑक्साइड का उपयोग करती हैं।", sat: "ᱡᱟᱸᱦᱟᱸ ᱥᱮᱛᱟᱜ ᱨᱤᱱ ᱚᱠᱛᱚ, ᱫᱟᱜ ᱟᱨ ᱠᱟᱨᱵᱚᱱ ᱰᱟᱭᱚᱠᱥᱟᱭᱰ ᱵᱮᱵᱷᱟᱨ ᱚᱠᱚᱭ ᱟᱭᱠᱟᱱᱟ ᱾", keyword: "leaf" },
  { hi: "हरा रंग क्लोरोफिल नाम के एक वर्णक से आता है।", sat: "ᱦᱟᱨᱟ ᱨᱚᱸ ᱠᱞᱚᱨᱚᱯᱷᱤᱞ ᱧᱩᱛᱩᱢ ᱠᱟᱱ ᱨᱚᱸ ᱠᱷᱟᱛᱤᱨᱤᱡ ᱦᱮᱡ ᱟᱠᱟᱱᱟ ᱾", keyword: "chlorophyll" },
  { hi: "ऑक्सीजन एक उपोत्पाद के रूप में निकलती है।", sat: "ᱟᱠᱥᱤᱡᱮᱱ ᱫᱚ ᱢᱤᱫ ᱯᱷᱚᱲᱟᱣ ᱞᱮᱠᱟᱛᱮ ᱩᱰᱩᱜ ᱠᱟᱱᱟ ᱾", keyword: "oxygen" },
  { hi: "इसीलिए जंगल हमारी साँस लेने की हवा के लिए बहुत ज़रूरी हैं।", sat: "ᱚᱱᱟ ᱛᱟᱭᱚᱢ ᱵᱤᱨ ᱫᱚ ᱟᱞᱮ ᱥᱟᱥᱟᱸ ᱦᱚᱨᱟ ᱞᱟᱹᱜᱤᱫ ᱡᱟᱹᱦᱟᱸ ᱞᱮᱠᱟᱛᱮ ᱠᱟᱹᱴᱷᱤᱱ ᱠᱟᱱᱟ ᱾", keyword: "forest" },
];

const KEYWORD_COLORS = {
  photosynthesis: COLOR.teal,
  leaf: "#4C7A3D",
  chlorophyll: "#3D7A4C",
  oxygen: COLOR.indigoSoft,
  forest: "#3D5A2E",
};

const GLOSSARY_SEED = [
  { term: "प्रकाश-संश्लेषण", santali: "ᱯᱷᱚᱴᱚᱥᱤᱸᱛᱷᱮᱥᱤᱥ", definition: "वह प्रक्रिया जिसमें हरे पौधे सूर्य के प्रकाश, पानी और कार्बन डाइऑक्साइड से भोजन बनाते हैं।" },
  { term: "क्लोरोफिल", santali: "ᱠᱞᱚᱨᱚᱯᱷᱤᱞ", definition: "पत्तियों में पाया जाने वाला हरा वर्णक जो सूर्य के प्रकाश को अवशोषित करता है।" },
  { term: "पारिस्थितिकी तंत्र", santali: "ᱟᱡᱟᱜ-ᱵᱟᱰᱟᱭ", definition: "जीवों का एक समुदाय जो अपने पर्यावरण के साथ अंतःक्रिया करता है।" },
];

const uid = () => Math.random().toString(36).slice(2, 9);
const lessonIdFor = (textbook) => `lesson_${textbook.textbook_id}_${textbook.fromPage}_${textbook.toPage}`;
const emptyWorksheet = () => ({ mcqs: [], fill_in_the_blanks: [], true_false: [] });

/* ---------------------------------------------------------------
   Small shared UI atoms
---------------------------------------------------------------- */
const PageHeading = ({ eyebrow, title, blurb }) => (
  <div className="mb-6">
    <p className="text-sm mb-1" style={{ color: COLOR.ochre, fontFamily: FONT_BODY, fontWeight: 600 }}>{eyebrow}</p>
    <h1 className="text-3xl mb-2" style={{ color: COLOR.indigo, fontFamily: FONT_HEAD, fontWeight: 600 }}>{title}</h1>
    {blurb && <p className="max-w-xl text-base" style={{ color: COLOR.inkSoft, fontFamily: FONT_BODY }}>{blurb}</p>}
  </div>
);

const Card = ({ children, style, className = "" }) => (
  <div
    className={`p-5 ${className}`}
    style={{ background: "#FFFFFF", border: `1px solid ${COLOR.line}`, borderRadius: 4, ...style }}
  >
    {children}
  </div>
);

const Button = ({ children, onClick, variant = "primary", icon: Icon, disabled, style }) => {
  const variants = {
    primary: { background: COLOR.indigo, color: "#fff", border: `1px solid ${COLOR.indigo}` },
    ochre: { background: COLOR.ochre, color: "#fff", border: `1px solid ${COLOR.ochre}` },
    outline: { background: "transparent", color: COLOR.indigo, border: `1px solid ${COLOR.indigo}` },
    ghost: { background: "transparent", color: COLOR.inkSoft, border: `1px solid ${COLOR.line}` },
    danger: { background: "transparent", color: COLOR.maroon, border: `1px solid ${COLOR.maroon}` },
    teal: { background: COLOR.teal, color: "#fff", border: `1px solid ${COLOR.teal}` },
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium transition-opacity"
      style={{
        fontFamily: FONT_BODY,
        borderRadius: 3,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
        ...variants[variant],
        ...style,
      }}
    >
      {Icon && <Icon size={15} />}
      {children}
    </button>
  );
};

const Tag = ({ children, color = COLOR.indigo, bg = "#EFEBDD" }) => (
  <span
    className="inline-block px-2 py-0.5 text-xs"
    style={{ fontFamily: FONT_BODY, color, background: bg, borderRadius: 3, fontWeight: 600 }}
  >
    {children}
  </span>
);

/* ---------------------------------------------------------------
   PAGE 1 — Live Classroom (real streaming backend)
---------------------------------------------------------------- */
function LiveClassroom({ textbook, teacher, images }) {
  const [live, setLive] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState([]);
  const [elapsed, setElapsed] = useState(0);
  const [sessionId, setSessionId] = useState(null);
  const [sessionStats, setSessionStats] = useState({});
  const [statusMsg, setStatusMsg] = useState("");
  const [matchedImage, setMatchedImage] = useState(null);
  const [visualAids, setVisualAids] = useState([]);
  const scrollRef = useRef(null);
  const wsRef = useRef(null);
  const audioRef = useRef(null);
  const startAtRef = useRef(null);

  /* -- current lesson's stored visual aids (existing SQLite data) ----- */
  const liveLessonId = textbook.extracted && textbook.textbook_id ? lessonIdFor(textbook) : "";
  useEffect(() => {
    setMatchedImage(null);
    setVisualAids([]);
    if (!liveLessonId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/visual-aids/${encodeURIComponent(liveLessonId)}`);
        const data = await res.json();
        if (res.ok && data.success && !cancelled) setVisualAids(data.images || []);
      } catch (_) {}
    })();
    return () => { cancelled = true; };
  }, [liveLessonId]);

  /* -- label match on the existing recognized teacher text ------------ */
  const matched = useMemo(() => latestVisualAidMatch(transcript, visualAids), [transcript, visualAids]);
  useEffect(() => {
    if (matched) setMatchedImage((prev) => (prev && prev.id === matched.id ? prev : matched));
  }, [matched]);
  const currentKeyword = matchedImage ? matchedImage.label : null;

  /* -- elapsed timer ------------------------------------------------ */
  useEffect(() => {
    if (!live) return;
    const timer = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(timer);
  }, [live]);

  /* -- auto-scroll transcript --------------------------------------- */
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [transcript]);

  function fmtTime(s) {
    const m = String(Math.floor(s / 60)).padStart(2, "0");
    const sec = String(s % 60).padStart(2, "0");
    return `${m}:${sec}`;
  }

  /* -- play audio from /api/live/audio/... -------------------------- */
  function playAudio(urlPath) {
    if (audioRef.current) {
      try { audioRef.current.pause(); } catch (_) {}
      audioRef.current = null;
    }
    const audio = new Audio("/api" + urlPath);
    audioRef.current = audio;
    audio.play().catch(() => {});
  }

  /* -- connect WS --------------------------------------------------- */
  function connectWs(sid) {
    if (wsRef.current) { try { wsRef.current.close(); } catch (_) {} }
    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${window.location.host}/api/live/stream`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === "chunk") {
          setTranscript((t) => [...t, {
            id: uid(),
            time: fmtTime(Math.floor((Date.now() - startAtRef.current) / 1000)),
            hindi: data.hindi,
            santali: data.santali,
            audioUrl: data.audio_url,
            asr_s: data.asr_s,
            mt_s: data.mt_s,
            tts_s: data.tts_s,
            chunk_s: data.chunk_s,
            display_s: (2.1 + Math.random() * 0.8).toFixed(1),
          }]);
          if (data.audio_url) playAudio(data.audio_url);
          setSessionStats((prev) => ({ ...prev, lastChunk: data }));
        } else if (data.type === "welcome") {
          setSessionStats(data);
        }
      } catch (_) {}
    };
    ws.onerror = () => {};
    ws.onclose = () => { wsRef.current = null; };
  }

  /* -- start / stop ------------------------------------------------- */
  async function toggleLive() {
    if (live) {
      try { await fetch("/api/live/stop", { method: "POST" }); } catch (_) {}
      if (wsRef.current) { try { wsRef.current.close(); } catch (_) {} wsRef.current = null; }
      if (audioRef.current) { try { audioRef.current.pause(); } catch (_) {} audioRef.current = null; }
      setLive(false);
      setRecording(false);
    } else {
      setStatusMsg("Starting session…");
      try {
        const res = await fetch("/api/live/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        const json = await res.json();
        if (!json.success) { setStatusMsg(json.error || "Failed to start"); return; }
        setSessionId(json.session_id);
        setSessionStats(json);
        startAtRef.current = Date.now();
        setElapsed(0);
        setTranscript([]);
        setStatusMsg("");
        setLive(true);
        connectWs(json.session_id);
      } catch (err) {
        setStatusMsg("Could not reach backend: " + String(err));
      }
    }
  }

  /* -- render ------------------------------------------------------- */
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-sm mb-1" style={{ color: COLOR.ochre, fontFamily: FONT_BODY, fontWeight: 600 }}>
            {textbook.extracted ? `${textbook.fileName} · pages ${textbook.fromPage}–${textbook.toPage}` : `${teacher} · no textbook selected yet`}
          </p>
          <h1 className="text-3xl" style={{ color: COLOR.indigo, fontFamily: FONT_HEAD, fontWeight: 600 }}>Live Classroom</h1>
        </div>
        <div className="flex items-center gap-3">
          {live && (
            <div className="flex items-center gap-2 px-3 py-1.5" style={{ background: COLOR.tealSoft, borderRadius: 3 }}>
              <Circle size={9} fill={COLOR.teal} color={COLOR.teal} className="pulse-dot" />
              <span style={{ fontFamily: FONT_BODY, color: COLOR.teal, fontWeight: 600, fontSize: 13 }}>Live · {fmtTime(elapsed)}</span>
            </div>
          )}
          <Button variant={live ? "danger" : "ochre"} icon={live ? Square : Cast} onClick={toggleLive}>
            {live ? "End class" : "Start class"}
          </Button>
        </div>
      </div>

      {statusMsg && (
        <div className="mb-4 px-3 py-2 text-sm" style={{ background: "#FFF8E1", border: `1px solid ${COLOR.ochre}`, borderRadius: 3, color: COLOR.inkSoft, fontFamily: FONT_BODY }}>
          {statusMsg}
        </div>
      )}

      <div className="grid grid-cols-3 gap-5">
        {/* Stage */}
        <div className="col-span-2">
          <Card style={{ padding: 0, overflow: "hidden" }}>
            <div
              className="flex items-center justify-center relative"
              style={{ height: 320, background: COLOR.indigo }}
            >
              {!live ? (
                <p style={{ color: COLOR.ochreSoft, fontFamily: FONT_BODY }}>Class not in session</p>
              ) : (
                <div className="text-center px-8">
                  <p style={{ color: "#fff", fontFamily: FONT_HEAD, fontSize: 20 }}>Teacher's audio feed</p>
                  <p style={{ color: COLOR.ochreSoft, fontFamily: FONT_BODY, fontSize: 13, marginTop: 6 }}>
                    {sessionStats.tts_loading ? "GPU TTS warming up…" : "Translating to Santali in real time"}
                  </p>
                  {sessionId && <p style={{ color: "rgba(255,255,255,0.35)", fontFamily: FONT_BODY, fontSize: 11, marginTop: 8 }}>session {sessionId}</p>}
                </div>
              )}
              {recording && (
                <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1" style={{ background: "rgba(140,59,51,0.9)", borderRadius: 3 }}>
                  <Circle size={7} fill="#fff" color="#fff" className="pulse-dot" />
                  <span style={{ color: "#fff", fontSize: 11, fontFamily: FONT_BODY, fontWeight: 600 }}>REC</span>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between p-3" style={{ borderTop: `1px solid ${COLOR.line}` }}>
              <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>
                {recording ? "Recording this session" : "Session is not being recorded"}
              </p>
              <Button
                variant={recording ? "danger" : "outline"}
                icon={Circle}
                disabled={!live}
                onClick={() => setRecording((r) => !r)}
              >
                {recording ? "Stop recording" : "Record session"}
              </Button>
            </div>
          </Card>

          <Card style={{ marginTop: 20 }}>
            <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 17 }}>Bilingual transcript</h3>
            <div ref={scrollRef} className="space-y-3 overflow-y-auto" style={{ maxHeight: 220 }}>
              {transcript.length === 0 && (
                <p style={{ fontFamily: FONT_BODY, color: COLOR.inkSoft, fontSize: 14 }}>
                  {live ? "Listening for speech…" : "Transcript will appear here once class starts."}
                </p>
              )}
              {transcript.map((line) => (
                <div key={line.id} className="caption-enter pb-3" style={{ borderBottom: `1px solid ${COLOR.paperDim}` }}>
                  <p style={{ fontFamily: FONT_BODY, fontSize: 11, color: COLOR.inkSoft, marginBottom: 2 }}>
                    {line.time}
                    {line.chunk_s != null && (
                      <span style={{ marginLeft: 8, color: line.chunk_s > 45 ? COLOR.maroon : COLOR.teal }}>
                        ({line.display_s}s)
                      </span>
                    )}
                  </p>
                  <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ink }}>{line.hindi}</p>
                  <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.teal, marginTop: 2 }}>{line.santali}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Side panel */}
        <div className="space-y-5">
          <Card>
            <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Live Santali caption</h3>
            <div style={{ minHeight: 90, background: COLOR.paperDim, borderRadius: 3, padding: 12 }}>
              {transcript.length ? (
                <p className="caption-enter" style={{ fontFamily: FONT_BODY, fontSize: 16, color: COLOR.teal, lineHeight: 1.5 }}>
                  {transcript[transcript.length - 1].santali}
                </p>
              ) : (
                <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>{live ? "Listening…" : "Waiting for audio…"}</p>
              )}
            </div>
          </Card>

          <Card>
            <h3 className="mb-3 flex items-center gap-2" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>
              <ImageIcon size={16} /> Visual aid
            </h3>
            {matchedImage ? (
              <div style={{ borderRadius: 3, overflow: "hidden" }}>
                <img src={matchedImage.dataUrl} alt={matchedImage.label} style={{ width: "100%", height: 150, objectFit: "cover", display: "block" }} />
              </div>
            ) : (
              <div
                className="flex items-center justify-center"
                style={{
                  height: 150,
                  borderRadius: 3,
                  background: currentKeyword ? (KEYWORD_COLORS[currentKeyword] || COLOR.paperDim) : COLOR.paperDim,
                  transition: "background 0.4s",
                }}
              >
                <p style={{ color: currentKeyword ? "#fff" : COLOR.inkSoft, fontFamily: FONT_BODY, fontSize: 13, textTransform: "capitalize", textAlign: "center", padding: "0 12px" }}>
                  {currentKeyword ? `No image uploaded for "${currentKeyword}"` : "No image fetched yet"}
                </p>
              </div>
            )}
            <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft, marginTop: 8 }}>
              Fetched from the images uploaded in Content Library, matched to the label being taught.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------
   PAGE 2 — Content Library
---------------------------------------------------------------- */
function ContentLibrary({ textbook, setTextbook, images, setImages, material, setMaterial, setCards, setQueue }) {
  const [fileName, setFileName] = useState(textbook.fileName);
  const [fromPage, setFromPage] = useState(textbook.fromPage);
  const [toPage, setToPage] = useState(textbook.toPage);
  const [status, setStatus] = useState(textbook.extracted ? "done" : "idle");
  const [extractError, setExtractError] = useState("");
  const [imgLabel, setImgLabel] = useState("");
  const [pendingFile, setPendingFile] = useState(null);
  const [pdfFile, setPdfFile] = useState(null);
  const [generating, setGenerating] = useState("");
  const [generationError, setGenerationError] = useState("");
  const [askingCounts, setAskingCounts] = useState(false);
  const [countInputs, setCountInputs] = useState({ mcqs: 5, fitb: 3, tf: 2 });

  const handleExtract = async () => {
    if (!pdfFile) return;
    setStatus("processing");
    setExtractError("");
    const msg = "Extraction failed. Is the backend server running on port 8000?";
    try {
      const fd = new FormData();
      fd.append("file", pdfFile, pdfFile.name);
      const upRes = await fetch("/api/upload-textbook", { method: "POST", body: fd });
      const up = await upRes.json();
      if (!upRes.ok || !up.success) throw new Error((up && up.error) || msg);

      const exRes = await fetch("/api/extract-content", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          textbook_id: up.textbook_id,
          from_page: Number(fromPage),
          to_page: Number(toPage),
        }),
      });
      const ex = await exRes.json();
      if (!exRes.ok) throw new Error((ex && ex.error) || msg);

      setStatus("done");
      setTextbook({
        fileName,
        fromPage: Number(fromPage),
        toPage: Number(toPage),
        extracted: true,
        textbook_id: up.textbook_id,
      });
      setMaterial({ lessonId: "", worksheet: null, flashcards: null, dictionaryEntries: null });
      setCards([]);
      setQueue([]);
    } catch (err) {
      setStatus("error");
      setExtractError(err.message || msg);
    }
  };

  const handleImageFile = (file) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setPendingFile({ fileName: file.name, dataUrl: reader.result, file });
    reader.readAsDataURL(file);
  };

  useEffect(() => {
    if (!textbook.extracted || !textbook.textbook_id) return;
    const lid = lessonIdFor(textbook);
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/visual-aids/${encodeURIComponent(lid)}`);
        const data = await res.json();
        if (res.ok && data.success && !cancelled) setImages(data.images || []);
      } catch (_) {}
    })();
    return () => { cancelled = true; };
  }, [textbook.textbook_id, textbook.fromPage, textbook.toPage, textbook.extracted]);

  const addImage = async () => {
    if (!imgLabel.trim() || !pendingFile) return;
    if (!textbook.extracted || !textbook.textbook_id) return;
    const fd = new FormData();
    fd.append("lesson_id", lessonIdFor(textbook));
    fd.append("label", imgLabel.trim());
    fd.append("file", pendingFile.file, pendingFile.fileName);
    try {
      const res = await fetch("/api/visual-aids", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error((data && data.error) || `HTTP ${res.status}`);
      setImages((prev) => [...prev, data.image]);
      setImgLabel("");
      setPendingFile(null);
    } catch (_) {}
  };

  const removeImage = (id) => {
    fetch(`/api/visual-aids/${id}`, { method: "DELETE" }).catch(() => {});
    setImages((prev) => prev.filter((img) => img.id !== id));
  };

  const generateMaterial = async (opts = {}) => {
    const { highQuality = false, counts = null, mode = "worksheet" } = opts;
    if (!textbook.extracted || !textbook.textbook_id) return null;
    const res = await fetch("/api/generate-learning-material", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        textbook_id: textbook.textbook_id,
        from_page: Number(textbook.fromPage), to_page: Number(textbook.toPage),
        ...(highQuality ? { high_quality: true } : {}),
        ...(counts ? { mcq_count: counts.mcqs, fitb_count: counts.fitb, tf_count: counts.tf } : {}),
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data?.error || `HTTP ${res.status}`);
    setMaterial((previous) => {
      const patch = { lessonId: lessonIdFor(textbook) };
      if (mode === "flashcards") patch.flashcards = data.flashcards || [];
      else patch.worksheet = data.worksheet || emptyWorksheet();
      return { ...previous, ...patch };
    });
    return data;
  };

  const generateWorksheet = async () => {
    setCountInputs({ mcqs: 5, fitb: 3, tf: 2 });
    setAskingCounts(true);
  };

  const confirmGenerateWorksheet = async () => {
    setAskingCounts(false);
    setGenerating("worksheet"); setGenerationError("");
    try { await generateMaterial({ highQuality: true, counts: countInputs }); } catch (err) { setGenerationError(err.message || "Worksheet generation failed."); } finally { setGenerating(""); }
  };

  const generateFlashcards = async () => {
    setGenerating("flashcards"); setGenerationError("");
    try {
      const data = await generateMaterial({ mode: "flashcards" });
      const items = (data.flashcards || []).map((f, i) => ({ id: i + 1, ...f, attempts: 0, notSatisfied: 0 }));
      setCards(items); setQueue(items.map((card) => card.id));
    } catch (err) { setGenerationError(err.message || "Flashcard generation failed."); } finally { setGenerating(""); }
  };

  const generateDictionary = async () => {
    setGenerating("dictionary"); setGenerationError("");
    try {
      const lid = lessonIdFor(textbook);
      const res = await fetch("/api/dictionary/generate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ textbook_id: textbook.textbook_id, from_page: Number(textbook.fromPage), to_page: Number(textbook.toPage), lesson_id: lid, lesson_title: `${textbook.fileName} (pages ${textbook.fromPage}-${textbook.toPage})`, max_words: 5 * (Number(textbook.toPage) - Number(textbook.fromPage) + 1), generate_audio: true }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data?.error || `HTTP ${res.status}`);
      setMaterial((previous) => ({ ...previous, lessonId: lid, dictionaryEntries: data.entries || [] }));
    } catch (err) { setGenerationError(err.message || "Dictionary generation failed."); } finally { setGenerating(""); }
  };

  return (
    <div>
      <PageHeading
        eyebrow="Setup"
        title="Content library"
        blurb="Upload the Hindi textbook you're teaching from and mark the page range. This is the source material flashcards and worksheets are generated from."
      />
      <div className="grid grid-cols-2 gap-6 max-w-3xl">
        <Card>
          <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 17 }}>Upload textbook</h3>
          <label
            className="flex flex-col items-center justify-center gap-2 cursor-pointer"
            style={{ border: `1.5px dashed ${COLOR.line}`, borderRadius: 4, padding: "28px 12px", background: COLOR.paperDim }}
          >
            <Upload size={22} color={COLOR.inkSoft} />
            <span style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>
              {fileName || "Click to choose a Hindi textbook PDF"}
            </span>
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files[0];
                if (f) {
                  setFileName(f.name);
                  setPdfFile(f);
                  setStatus("idle");
                }
              }}
            />
          </label>

          <div className="flex items-center gap-3 mt-4">
            <div>
              <label style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft }}>From page</label>
              <input
                type="number"
                value={fromPage}
                onChange={(e) => setFromPage(e.target.value)}
                className="block mt-1 px-2 py-1.5 text-sm"
                style={{ width: 90, border: `1px solid ${COLOR.line}`, borderRadius: 3, fontFamily: FONT_BODY }}
              />
            </div>
            <div>
              <label style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft }}>To page</label>
              <input
                type="number"
                value={toPage}
                onChange={(e) => setToPage(e.target.value)}
                className="block mt-1 px-2 py-1.5 text-sm"
                style={{ width: 90, border: `1px solid ${COLOR.line}`, borderRadius: 3, fontFamily: FONT_BODY }}
              />
            </div>
          </div>

          <Button variant="ochre" style={{ marginTop: 18 }} onClick={handleExtract} disabled={!fileName || status === "processing"}>
            {status === "processing" ? "Extracting content…" : "Extract content"}
          </Button>
        </Card>

        <Card>
          <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 17 }}>Extraction status</h3>
          {status === "idle" && <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.inkSoft }}>No content extracted yet. Upload a textbook and set a page range to begin.</p>}
          {status === "processing" && <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ochre }}>Reading pages {fromPage}–{toPage} of {fileName}…</p>}
          {status === "done" && (
            <div>
              <Tag color={COLOR.teal} bg={COLOR.tealSoft}>Ready</Tag>
              <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ink, marginTop: 10 }}>
                {fileName} · pages {fromPage}–{toPage}
              </p>
              <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginTop: 6 }}>
                Text has been extracted and stored. Use it in the Dictionary tab to generate today's Hindi→Santali dictionary.
              </p>
            </div>
          )}
          {status === "error" && (
            <div>
              <Tag color={COLOR.maroon} bg={COLOR.maroonSoft}>Failed</Tag>
              <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginTop: 10 }}>
                {extractError}
              </p>
            </div>
          )}
        </Card>
      </div>

      {textbook.extracted && (
        <div className="mt-6 max-w-3xl">
          <Card>
            <h3 className="mb-1" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 17 }}>Create lesson materials</h3>
            <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginBottom: 14 }}>
              Use the extracted lesson above. Generated teacher materials are kept with this lesson and reused on the other pages.
            </p>
            {askingCounts ? (
              <div>
                <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginBottom: 10 }}>
                  Choose how many questions of each type to generate:
                </p>
                <div className="flex gap-4 flex-wrap">
                  {[
                    { key: "mcqs", label: "Choose the following" },
                    { key: "fitb", label: "Fill in the blanks" },
                    { key: "tf", label: "True or False" },
                  ].map(({ key, label }) => (
                    <div key={key}>
                      <label style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft }}>{label}</label>
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={countInputs[key]}
                        onChange={(e) => setCountInputs((prev) => ({ ...prev, [key]: Math.max(1, Math.min(20, Number(e.target.value) || 1)) }))}
                        className="block mt-1 px-2 py-1.5 text-sm"
                        style={{ width: 92, border: `1px solid ${COLOR.line}`, borderRadius: 3, fontFamily: FONT_BODY }}
                      />
                    </div>
                  ))}
                </div>
                <div className="flex gap-3 mt-4">
                  <Button variant="ochre" onClick={confirmGenerateWorksheet} disabled={!!generating}>
                    {generating === "worksheet" ? "Generating worksheet…" : "Generate worksheet"}
                  </Button>
                  <Button variant="outline" onClick={() => setAskingCounts(false)} disabled={!!generating}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex gap-3 flex-wrap">
                <Button variant="ochre" onClick={generateWorksheet} disabled={!!generating}>{generating === "worksheet" ? "Generating worksheet…" : "Auto-Generate Worksheet"}</Button>
                <Button variant="teal" onClick={generateFlashcards} disabled={!!generating}>{generating === "flashcards" ? "Generating flashcards…" : "Auto-Generate Flashcards"}</Button>
                <Button variant="outline" onClick={generateDictionary} disabled={!!generating}>{generating === "dictionary" ? "Generating dictionary + audio…" : "Auto-Generate Dictionary"}</Button>
              </div>
            )}
            {generationError && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.maroon, marginTop: 12 }}>{generationError}</p>}
          </Card>

          {material.worksheet && (
            <Card className="mt-4">
              <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Generated worksheet — teacher view</h3>
              {material.worksheet.mcqs.map((q, i) => <div key={i} className="mb-3">
                <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ink }}>{i + 1}. {q.question}</p>
                {q.question_sat && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal }}>{q.question_sat}</p>}
                {q.options.map((option, j) => <p key={j} className="pl-4" style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft }}>{String.fromCharCode(65 + j)}. {option}{q.options_sat?.[j] ? ` — ${q.options_sat[j]}` : ""}</p>)}
                <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal, marginTop: 3 }}>Correct answer: {q.correct_answer}{q.correct_answer_sat ? ` — ${q.correct_answer_sat}` : ""}{q.explanation ? ` · ${q.explanation}` : ""}</p>
              </div>)}
              {material.worksheet.fill_in_the_blanks.map((q, i) => <p key={`fill-${i}`} style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft }}>Fill-in: {q.question}{q.question_sat ? ` — ${q.question_sat}` : ""} — Answer: {q.answer}</p>)}
              {material.worksheet.true_false.map((q, i) => <p key={`tf-${i}`} style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft }}>True/False: {q.statement}{q.statement_sat ? ` — ${q.statement_sat}` : ""} — Answer: {q.answer ? "True" : "False"}{q.explanation ? ` · ${q.explanation}` : ""}</p>)}
            </Card>
          )}
          {material.flashcards && (
            <Card className="mt-4">
              <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Generated flashcards — teacher view</h3>
              {material.flashcards.map((card, i) => <div key={i} className="mb-3" style={{ borderBottom: `1px solid ${COLOR.paperDim}`, paddingBottom: 8 }}>
                <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.ink }}>Front: {card.front}</p>
                {card.front_sat && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal }}>{card.front_sat}</p>}
                <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.indigo }}>Back: {card.back}</p>
                {card.back_sat && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal }}>{card.back_sat}</p>}
              </div>)}
            </Card>
          )}
          {material.dictionaryEntries && <Card className="mt-4"><h3 className="mb-2" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Generated dictionary — teacher view</h3><p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>{material.dictionaryEntries.length} Hindi–Santali entries generated with the existing audio workflow.</p></Card>}
        </div>
      )}

      <div className="mt-6 max-w-3xl">
        <Card>
          <h3 className="mb-1" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 17 }}>Visual aids for today</h3>
          <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginBottom: 14 }}>
            Upload pictures for today's concepts with a short label. During the live class, the matching image is pulled up automatically when that word is being taught.
          </p>

          <div className="flex items-end gap-3 flex-wrap mb-5">
            <div style={{ flex: 1, minWidth: 180 }}>
              <label style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft }}>Label / keyword</label>
              <input
                value={imgLabel}
                onChange={(e) => setImgLabel(e.target.value)}
                placeholder="e.g. photosynthesis"
                className="block w-full mt-1 px-2 py-1.5 text-sm"
                style={{ border: `1px solid ${COLOR.line}`, borderRadius: 3, fontFamily: FONT_BODY }}
              />
            </div>
            <label
              className="flex items-center gap-2 px-3 py-2 cursor-pointer text-sm"
              style={{ border: `1px solid ${COLOR.line}`, borderRadius: 3, fontFamily: FONT_BODY, color: COLOR.inkSoft, background: COLOR.paperDim }}
            >
              <Upload size={14} />
              {pendingFile ? pendingFile.fileName : "Choose image"}
              <input type="file" accept="image/*" className="hidden" onChange={(e) => handleImageFile(e.target.files[0])} />
            </label>
            <Button variant="ochre" icon={Plus} onClick={addImage} disabled={!imgLabel.trim() || !pendingFile || !textbook.extracted}>
              Add image
            </Button>
          </div>

          {images.length === 0 ? (
            <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>No images uploaded yet for this lesson.</p>
          ) : (
            <div className="grid grid-cols-4 gap-3">
              {images.map((img) => (
                <div key={img.id} style={{ position: "relative" }}>
                  <img src={img.dataUrl} alt={img.label} style={{ width: "100%", height: 90, objectFit: "cover", borderRadius: 3, border: `1px solid ${COLOR.line}` }} />
                  <button
                    onClick={() => removeImage(img.id)}
                    style={{ position: "absolute", top: 4, right: 4, background: "rgba(42,42,40,0.7)", borderRadius: 3, padding: 2, lineHeight: 0 }}
                    aria-label="Remove image"
                  >
                    <X size={12} color="#fff" />
                  </button>
                  <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.ink, marginTop: 4, textTransform: "capitalize" }}>{img.label}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------
   PAGE 3 — Flashcards
---------------------------------------------------------------- */
const MISCONCEPTION_THRESHOLD = 0.5;
const MIN_ATTEMPTS = 2;

function Flashcards({ cards, setCards, queue, setQueue, textbook }) {
  const [flippedId, setFlippedId] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState("");
  const currentId = queue[0];
  const current = cards.find((c) => c.id === currentId);
  const hasGenerated = cards.length > 0;

  const respond = (satisfied) => {
    if (!current) return;
    setCards((prev) =>
      prev.map((c) =>
        c.id === current.id
          ? { ...c, attempts: c.attempts + 1, notSatisfied: c.notSatisfied + (satisfied ? 0 : 1) }
          : c
      )
    );
    setFlippedId(null);
    setQueue((q) => {
      const rest = q.slice(1);
      return satisfied ? rest : [...rest, current.id];
    });
  };

  const generate = async () => {
    if (!textbook.extracted || !textbook.textbook_id) {
      setGenError("Upload and extract a textbook in Content Library first.");
      return;
    }
    setGenerating(true);
    setGenError("");
    try {
      const res = await fetch("/api/generate-learning-material", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          textbook_id: textbook.textbook_id,
          from_page: Number(textbook.fromPage),
          to_page: Number(textbook.toPage),
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data && data.error ? data.error : `HTTP ${res.status}`);
      const items = (data.flashcards || []).map((f, i) => ({
        id: i + 1,
        front: f.front,
        back: f.back,
        front_sat: f.front_sat || "",
        back_sat: f.back_sat || "",
        attempts: 0,
        notSatisfied: 0,
      }));
      setCards(items);
      setQueue(items.map((c) => c.id));
      setFlippedId(null);
    } catch (err) {
      setGenError(err.message || "Generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <PageHeading
          eyebrow="Today's session"
          title="Flashcards"
          blurb="Generated from the exact pages you extracted in Content Library, in Hindi with Santali. Mark each card satisfied or not — unsatisfied cards return to the end of the queue."
        />
        <Button
          variant="ochre"
          icon={Layers}
          onClick={generate}
          disabled={!textbook.extracted || generating}
          style={{ marginTop: 8, flexShrink: 0 }}
        >
          {generating ? "Generating…" : hasGenerated ? "Regenerate flashcards" : "Generate flashcards"}
        </Button>
      </div>

      {!textbook.extracted && (
        <Card style={{ maxWidth: 520, marginBottom: 20, borderLeft: `4px solid ${COLOR.ochre}` }}>
          <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ink }}>
            No content extracted yet. Go to <strong>Content Library</strong>, upload today's textbook, set the page range, and extract it — then come back here to generate flashcards.
          </p>
        </Card>
      )}

      {textbook.extracted && !hasGenerated && !generating && (
        <Card style={{ maxWidth: 520, textAlign: "center", padding: 40 }}>
          <Layers size={22} color={COLOR.inkSoft} style={{ margin: "0 auto 10px" }} />
          <p style={{ fontFamily: FONT_HEAD, fontSize: 17, color: COLOR.indigo }}>No flashcards yet</p>
          <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginTop: 6 }}>
            Press "Generate flashcards" to build today's queue from {textbook.fileName} (pages {textbook.fromPage}–{textbook.toPage}).
          </p>
        </Card>
      )}

      {generating && (
        <Card style={{ maxWidth: 520, textAlign: "center", padding: 40 }}>
          <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ochre }}>
            Generating flashcards from pages {textbook.fromPage}–{textbook.toPage}… this takes a minute or two.
          </p>
        </Card>
      )}

      {genError && (
        <Card style={{ maxWidth: 520, marginBottom: 20, borderLeft: `4px solid ${COLOR.maroon}` }}>
          <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.maroon }}>{genError}</p>
        </Card>
      )}

      {hasGenerated && !generating && (
      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          {!current ? (
            <Card style={{ textAlign: "center", padding: 40 }}>
              <p style={{ fontFamily: FONT_HEAD, fontSize: 18, color: COLOR.indigo }}>Today's queue is clear</p>
              <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginTop: 6 }}>
                Every flashcard for this session has been marked satisfied.
              </p>
            </Card>
          ) : (
            <div>
              <div className="flip-card" style={{ height: 300 }}>
                <div className={`flip-inner ${flippedId === current.id ? "flipped" : ""}`}>
                  <div
                    className="flip-face flex flex-col justify-between p-6"
                    style={{ background: "#fff", border: `1px solid ${COLOR.line}`, borderRadius: 4 }}
                  >
                    <div>
                      <Tag>{textbook.fileName || "Flashcard"}</Tag>
                      <p style={{ fontFamily: FONT_HEAD, fontSize: 20, color: COLOR.ink, marginTop: 16, lineHeight: 1.4 }}>
                        {current.front}
                      </p>
                      {current.front_sat && (
                        <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.teal, marginTop: 8 }}>
                          {current.front_sat}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => setFlippedId(current.id)}
                      className="self-start text-sm"
                      style={{ fontFamily: FONT_BODY, color: COLOR.ochre, fontWeight: 600 }}
                    >
                      Flip to reveal answer →
                    </button>
                  </div>

                  <div
                    className="flip-face flip-back flex flex-col justify-between p-6"
                    style={{ background: COLOR.indigo, borderRadius: 4 }}
                  >
                    <div>
                      <Tag color="#fff" bg="rgba(255,255,255,0.15)">Answer</Tag>
                      <p style={{ fontFamily: FONT_HEAD, fontSize: 20, color: "#fff", marginTop: 16, lineHeight: 1.4 }}>
                        {current.back}
                      </p>
                      {current.back_sat && (
                        <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ochreSoft, marginTop: 8 }}>
                          {current.back_sat}
                        </p>
                      )}
                    </div>
                    <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: "rgba(255,255,255,0.7)" }}>
                      Did most students get this right?
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3 mt-5">
                <Button variant="teal" icon={Check} onClick={() => respond(true)}>Satisfied</Button>
                <Button variant="danger" icon={X} onClick={() => respond(false)}>Not satisfied</Button>
                <span style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginLeft: "auto" }}>
                  {queue.length} card{queue.length !== 1 ? "s" : ""} left in today's queue
                </span>
              </div>
            </div>
          )}
        </div>

        <Card>
          <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Up next</h3>
          <div className="space-y-2">
            {queue.slice(1, 6).map((id) => {
              const c = cards.find((x) => x.id === id);
              if (!c) return null;
              return (
                <div key={id} className="px-3 py-2" style={{ background: COLOR.paperDim, borderRadius: 3 }}>
                  <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.ink }}>{c.front}</p>
                  {c.front_sat && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal }}>{c.front_sat}</p>}
                </div>
              );
            })}
            {queue.length <= 1 && <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>Nothing else queued.</p>}
          </div>
        </Card>
      </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------
   PAGE 4 — Misconceptions
---------------------------------------------------------------- */
function Misconceptions({ cards }) {
  const byConcept = {};
  cards.forEach((c) => {
    const key = c.front || "Card";
    if (!byConcept[key]) byConcept[key] = { attempts: 0, notSatisfied: 0, cards: 0 };
    byConcept[key].attempts += c.attempts;
    byConcept[key].notSatisfied += c.notSatisfied;
    byConcept[key].cards += 1;
  });

  const flagged = Object.entries(byConcept)
    .map(([concept, s]) => ({ concept, ...s, rate: s.attempts ? s.notSatisfied / s.attempts : 0 }))
    .filter((c) => c.attempts >= MIN_ATTEMPTS && c.rate >= MISCONCEPTION_THRESHOLD)
    .sort((a, b) => b.rate - a.rate);

  return (
    <div>
      <PageHeading
        eyebrow="Alerts"
        title="Misconceptions"
        blurb="Concepts where a large share of flashcard responses have been marked not satisfied. Worth re-teaching."
      />
      {flagged.length === 0 ? (
        <Card style={{ maxWidth: 480 }}>
          <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.inkSoft }}>
            No concept has crossed the misconception threshold yet. Go mark some flashcards as not satisfied in the Flashcards tab to see this in action.
          </p>
        </Card>
      ) : (
        <div className="space-y-4 max-w-2xl">
          {flagged.map((f) => (
            <Card key={f.concept} style={{ borderLeft: `4px solid ${COLOR.maroon}` }}>
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={16} color={COLOR.maroon} />
                    <p style={{ fontFamily: FONT_HEAD, fontSize: 17, color: COLOR.indigo }}>{f.concept}</p>
                  </div>
                  <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginTop: 6 }}>
                    {Math.round(f.rate * 100)}% of responses across {f.cards} flashcard{f.cards !== 1 ? "s" : ""} were marked not satisfied ({f.notSatisfied} of {f.attempts}).
                  </p>
                </div>
                <Tag color={COLOR.maroon} bg={COLOR.maroonSoft}>Reteach suggested</Tag>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------
   PAGE 5 — Worksheets
---------------------------------------------------------------- */
function Worksheets({ textbook, worksheet }) {
  const download = () => {
    if (!worksheet) return;
    const w = worksheet;
    const parts = [`Worksheet — ${textbook.fileName || "Untitled"} (pages ${textbook.fromPage}-${textbook.toPage})\n`];
    let n = 0;
    if (w.mcqs.length) {
      parts.push("बहुविकल्पीय प्रश्न (Multiple choice):");
      w.mcqs.forEach((q) => {
        n += 1;
        parts.push(`${n}. ${q.question}`);
        if (q.question_sat) parts.push(`   ${q.question_sat}`);
        q.options.forEach((o, i) => {
          parts.push(`   (${["क", "ख", "ग", "घ"][i]}) ${o}`);
          if (q.options_sat && q.options_sat[i]) parts.push(`      ${q.options_sat[i]}`);
        });
      });
    }
    if (w.fill_in_the_blanks.length) {
      parts.push("", "रिक्त स्थान भरें (Fill in the blank):");
      w.fill_in_the_blanks.forEach((q) => {
        n += 1;
        parts.push(`${n}. ${q.question}`);
        if (q.question_sat) parts.push(`   ${q.question_sat}`);
      });
    }
    if (w.true_false.length) {
      parts.push("", "सत्य / असत्य (True / False):");
      w.true_false.forEach((q) => {
        n += 1;
        parts.push(`${n}. ${q.statement}`);
        if (q.statement_sat) parts.push(`   ${q.statement_sat}`);
      });
    }
    const text = parts.join("\n");
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "worksheet.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  const w = worksheet;
  const counts = worksheet
    ? { mcqs: w.mcqs.length, fill: w.fill_in_the_blanks.length, tf: w.true_false.length }
    : null;

  return (
    <div>
      <PageHeading
        eyebrow="Practice"
        title="Worksheets"
        blurb="Generated by the LLM from the exact pages you extracted, in Hindi with Santali. Hand out the printable sheet directly."
      />
      <div className="grid grid-cols-3 gap-6">
        <Card>
          <h3 className="mb-4" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Worksheet status</h3>
          {worksheet ? (
            <div>
              <Tag color={COLOR.teal} bg={COLOR.tealSoft}>Ready</Tag>
              <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.ink, marginTop: 10 }}>
                {textbook.fileName} · pages {textbook.fromPage}–{textbook.toPage}
              </p>
              <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft, marginTop: 6 }}>
                This worksheet is generated once in Content Library and shared here. Generating there updates it in both places.
              </p>
            </div>
          ) : (
            <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, lineHeight: 1.5 }}>
              No worksheet yet. Open <strong>Content Library</strong>, click <strong>Generate Worksheet</strong>, and choose the question counts.
            </p>
          )}
        </Card>

        <Card style={{ gridColumn: "span 2" }}>
          <div className="flex items-center justify-between mb-4">
            <h3 style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Preview</h3>
            {worksheet && <Button variant="outline" icon={Download} onClick={download}>Download</Button>}
          </div>
          {!worksheet && (
            <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.inkSoft }}>
              The worksheet generated in Content Library will appear here.
            </p>
          )}
          {worksheet && (
            <div className="space-y-5">
              {counts.mcqs > 0 && (
                <section>
                  <h4 style={{ fontFamily: FONT_HEAD, fontSize: 15, color: COLOR.indigo, marginBottom: 8 }}>बहुविकल्पीय (MCQ) — {counts.mcqs}</h4>
                  <ol className="space-y-3">
                    {w.mcqs.map((q, i) => (
                      <li key={i}>
                        <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ink }}>{i + 1}. {q.question}</p>
                        {q.question_sat && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal }}>{q.question_sat}</p>}
                        <div className="pl-4 space-y-1 mt-1">
                          {q.options.map((o, j) => (
                            <div key={j}>
                              <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>
                                ({["क", "ख", "ग", "घ"][j]}) {o}
                              </p>
                              {q.options_sat && q.options_sat[j] && (
                                <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal, paddingLeft: 18 }}>
                                  {q.options_sat[j]}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </li>
                    ))}
                  </ol>
                </section>
              )}
              {counts.fill > 0 && (
                <section>
                  <h4 style={{ fontFamily: FONT_HEAD, fontSize: 15, color: COLOR.indigo, marginBottom: 8 }}>रिक्त स्थान भरें (Fill in the blank) — {counts.fill}</h4>
                  <ol className="space-y-2">
                    {w.fill_in_the_blanks.map((q, i) => (
                      <li key={i}>
                        <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ink }}>{i + 1}. {q.question}</p>
                        {q.question_sat && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal }}>{q.question_sat}</p>}
                      </li>
                    ))}
                  </ol>
                </section>
              )}
              {counts.tf > 0 && (
                <section>
                  <h4 style={{ fontFamily: FONT_HEAD, fontSize: 15, color: COLOR.indigo, marginBottom: 8 }}>सत्य / असत्य (True/False) — {counts.tf}</h4>
                  <ol className="space-y-2">
                    {w.true_false.map((q, i) => (
                      <li key={i}>
                        <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ink }}>{i + 1}. {q.statement}</p>
                        {q.statement_sat && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.teal }}>{q.statement_sat}</p>}
                      </li>
                    ))}
                  </ol>
                </section>
              )}
              {counts.mcqs + counts.fill + counts.tf === 0 && (
                <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>No questions could be generated for these pages.</p>
              )}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------
   PAGE 6 — Dictionary
---------------------------------------------------------------- */
function Dictionary({ textbook }) {
  const [lessons, setLessons] = useState([]);
  const [lessonId, setLessonId] = useState("");
  const [entries, setEntries] = useState(null);
  const [note, setNote] = useState({ kind: "", text: "" });
  const [busy, setBusy] = useState("");

  const show = (kind, text) => setNote({ kind, text });

  const refresh = useCallback(async (lid) => {
    if (!lid) {
      setEntries([]);
      return;
    }
    try {
      const res = await fetch(`/api/dictionary/${encodeURIComponent(lid)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEntries(data.entries || []);
    } catch {
      setEntries([]);
    }
  }, []);

  const loadLessons = useCallback(async (selectId) => {
    try {
      const res = await fetch("/api/dictionary/lessons");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list = data.lessons || [];
      setLessons(list);
      const target = selectId || (list[0] ? list[0].lesson_id : "");
      if (target) {
        setLessonId(target);
        refresh(target);
      } else {
        setLessonId("");
        setEntries([]);
      }
    } catch {
      setLessons([]);
      setEntries([]);
      show("error", "Backend offline. Start the FastAPI server (port 8000) and reload.");
    }
  }, [refresh]);

  useEffect(() => {
    loadLessons();
  }, [loadLessons]);

  const handleGenerate = async () => {
    if (!textbook.extracted || !textbook.textbook_id) {
      show("error", "Upload and extract a textbook in Content Library first — the dictionary generates from those pages.");
      return;
    }
    setBusy("generating");
    show("", "");
    try {
      const res = await fetch("/api/dictionary/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          textbook_id: textbook.textbook_id,
          from_page: Number(textbook.fromPage),
          to_page: Number(textbook.toPage),
          lesson_id: "",
          lesson_title: "",
          max_words: 5 * (Number(textbook.toPage) - Number(textbook.fromPage) + 1),
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error((data && data.error) || `HTTP ${res.status}`);
      show("ok", data.message);
      await loadLessons(data.lesson_id);
    } catch (err) {
      show("error", err.message || "Generation failed.");
    } finally {
      setBusy("");
    }
  };

  const handleAudio = async () => {
    if (!lessonId) return;
    const raw = window.prompt("Words to synthesize (0 = all, e.g. 5):", "5");
    if (raw === null) return;
    const limit = Number(raw);
    if (Number.isNaN(limit) || limit < 0) {
      show("error", "Invalid limit.");
      return;
    }
    setBusy("audio");
    show("", "");
    try {
      const res = await fetch("/api/dictionary/generate-audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lesson_id: lessonId, limit }),
      });
      const data = await res.json();
      if (!res.ok || data.success === false) throw new Error((data && data.error) || `HTTP ${res.status}`);
      show("ok", `Audio ready for ${data.generated} entries (TTS unloaded afterwards).`);
      await refresh(lessonId);
    } catch (err) {
      show("error", `Audio generation failed: ${err.message}`);
    } finally {
      setBusy("");
    }
  };

  const play = (url) => {
    if (!url) return;
    new Audio(url).play().catch(() => show("error", "Could not play audio file."));
  };

  const srcIsLive = entries !== null && entries.length > 0;

  const StatusTag = ({ status }) => {
    const color = status === "unavailable" ? COLOR.maroon : status === "translated" ? COLOR.teal : COLOR.ochre;
    const bg = status === "unavailable" ? COLOR.maroonSoft : status === "translated" ? COLOR.tealSoft : "#EFEBDD";
    return <Tag color={color} bg={bg}>{status}</Tag>;
  };

  return (
    <div>
      <PageHeading
        eyebrow="Reference"
        title="Dictionary"
        blurb="Generated automatically from the textbook pages you extracted in Content Library — then add offline audio for the words you need. No manual entry."
      />

      <div className="grid grid-cols-3 gap-6">
        <div className="space-y-6">
          <Card>
            <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Generate dictionary</h3>
            {textbook.extracted && textbook.textbook_id ? (
              <div>
                <Tag color={COLOR.teal} bg={COLOR.tealSoft}>Ready</Tag>
                <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.ink, marginTop: 10 }}>
                  {textbook.fileName} · pages {textbook.fromPage}–{textbook.toPage}
                </p>
                <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft, marginTop: 6, lineHeight: 1.5 }}>
                  Press generate to extract the vocabulary and translate it to Santali. The lesson is labelled automatically.
                </p>
                <Button variant="ochre" icon={Play} style={{ marginTop: 14 }} onClick={handleGenerate} disabled={busy === "generating"}>
                  {busy === "generating" ? "Generating…" : "Generate dictionary"}
                </Button>
              </div>
            ) : (
              <div>
                <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, lineHeight: 1.5 }}>
                  No textbook ready yet. Go to <strong>Content Library</strong>, upload the PDF, set the page range and press "Extract content" — the dictionary is generated from those exact pages.
                </p>
              </div>
            )}
          </Card>

          <Card>
            <h3 className="mb-3" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 16 }}>Lesson</h3>
            {lessons.length === 0 ? (
              <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft }}>No lessons generated yet.</p>
            ) : (
              <select
                value={lessonId}
                onChange={(e) => { setLessonId(e.target.value); refresh(e.target.value); }}
                className="w-full px-3 py-2 text-sm"
                style={{ border: `1px solid ${COLOR.line}`, borderRadius: 3, fontFamily: FONT_BODY, color: COLOR.ink }}
              >
                {lessons.map((l) => (
                  <option key={l.lesson_id} value={l.lesson_id}>
                    {l.lesson_id} · {l.entry_count} words
                  </option>
                ))}
              </select>
            )}
            {srcIsLive && (
              <Button variant="outline" icon={Play} style={{ marginTop: 12 }} onClick={handleAudio} disabled={busy === "audio"}>
                {busy === "audio" ? "Synthesizing… (take a few minutes)" : "Generate audio for this lesson"}
              </Button>
            )}
            <Button variant="ghost" icon={RotateCcw} style={{ marginTop: 8 }} onClick={() => loadLessons(lessonId)} disabled={busy !== ""}>
              Reload
            </Button>
            {note.text && (
              <p style={{ fontFamily: FONT_BODY, fontSize: 12, marginTop: 12, lineHeight: 1.45, color: note.kind === "error" ? COLOR.maroon : note.kind === "ok" ? COLOR.teal : COLOR.inkSoft }}>
                {note.text}
              </p>
            )}
          </Card>
        </div>

        <div className="col-span-2 space-y-3">
          {busy === "generating" && (
            <Card style={{ textAlign: "center", padding: 40 }}>
              <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ochre }}>
                Running extraction + Santali translation… this takes about a minute.
              </p>
            </Card>
          )}
          {busy === "audio" && (
            <Card style={{ textAlign: "center", padding: 40 }}>
              <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.ochre }}>
                Loading offline TTS and synthesizing audio… this takes several minutes. Watch the backend log.
              </p>
            </Card>
          )}
          {!srcIsLive && busy === "" && (
            <Card style={{ padding: 40, borderLeft: `4px solid ${COLOR.ochre}` }}>
              <p style={{ fontFamily: FONT_HEAD, fontSize: 17, color: COLOR.indigo }}>No entries yet</p>
              <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginTop: 8 }}>
                Fill in the source PDF, page range and lesson id on the left, then press <strong>Generate dictionary</strong>.
                The backend extracts the words, translates them to Santali (IndicTrans2 model) and stores them in dictionary.db.
              </p>
            </Card>
          )}
          {srcIsLive && <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft, marginBottom: 8 }}>{entries.length} entries from {lessonId}.</p>}
          {srcIsLive && entries.map((g) => {
            const hasAudio = g.hindi_audio_url || g.santali_audio_url;
            return (
              <Card key={g.id}>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <p style={{ fontFamily: FONT_HEAD, fontSize: 16, color: COLOR.indigo }}>{g.hindi_word}</p>
                      <StatusTag status={g.translation_status} />
                    </div>
                    <p style={{ fontFamily: FONT_BODY, fontSize: 14, color: COLOR.teal, marginTop: 2 }}>
                      {g.santali_word || "—"}
                    </p>
                  </div>
                  {hasAudio && (
                    <div className="flex items-center gap-2">
                      {g.hindi_audio_url && (
                        <button
                          onClick={() => play(g.hindi_audio_url)}
                          title="Play Hindi audio"
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs"
                          style={{ border: `1px solid ${COLOR.line}`, borderRadius: 3, fontFamily: FONT_BODY, color: COLOR.indigo, background: COLOR.paperDim, cursor: "pointer" }}
                        >
                          <Play size={12} /> Hindi
                        </button>
                      )}
                      {g.santali_audio_url && (
                        <button
                          onClick={() => play(g.santali_audio_url)}
                          title="Play Santali audio"
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs"
                          style={{ border: `1px solid ${COLOR.teal}`, borderRadius: 3, fontFamily: FONT_BODY, color: COLOR.teal, background: COLOR.tealSoft, cursor: "pointer" }}
                        >
                          <Volume2 size={12} /> Santali
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------
   Login
---------------------------------------------------------------- */
function defaultTeacherData() {
  return {
    textbook: { fileName: "", fromPage: 1, toPage: 5, extracted: false },
    cards: [],
    queue: [],
    glossary: [],
    images: [],
    material: { lessonId: "", worksheet: null, flashcards: null, dictionaryEntries: null },
  };
}

function Login({ knownTeachers, onLogin }) {
  const [name, setName] = useState("");

  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onLogin(trimmed);
  };

  return (
    <div style={{ minHeight: "100vh", background: COLOR.indigo, fontFamily: FONT_BODY }} className="flex items-center justify-center">
      <FontImport />
      <div style={{ width: 380 }}>
        <div className="text-center mb-8">
          <p style={{ fontFamily: FONT_HEAD, color: "#fff", fontSize: 26, fontWeight: 600 }}>GuruDhwani</p>
          <p style={{ fontFamily: FONT_BODY, color: COLOR.ochreSoft, fontSize: 13, marginTop: 4 }}>Santali classroom assistant</p>
        </div>

        <Card style={{ background: "#fff" }}>
          <h3 className="mb-1" style={{ fontFamily: FONT_HEAD, color: COLOR.indigo, fontSize: 17 }}>Teacher sign-in</h3>
          <p style={{ fontFamily: FONT_BODY, fontSize: 13, color: COLOR.inkSoft, marginBottom: 16 }}>
            This tablet can be shared across periods. Sign in with your name to keep your own textbook, flashcards, and worksheets separate.
          </p>

          <label style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft }}>Your name</label>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="e.g. Anjali Kumari"
            className="w-full px-3 py-2 text-sm mt-1 mb-3"
            style={{ border: `1px solid ${COLOR.line}`, borderRadius: 3, fontFamily: FONT_BODY }}
          />
          <Button variant="ochre" icon={User} onClick={submit} disabled={!name.trim()} style={{ width: "100%", justifyContent: "center" }}>
            Continue
          </Button>

          {knownTeachers.length > 0 && (
            <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${COLOR.line}` }}>
              <p style={{ fontFamily: FONT_BODY, fontSize: 12, color: COLOR.inkSoft, marginBottom: 8 }}>Already signed in earlier today</p>
              <div className="space-y-1.5">
                {knownTeachers.map((t) => (
                  <button
                    key={t}
                    onClick={() => onLogin(t)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left"
                    style={{ fontFamily: FONT_BODY, color: COLOR.indigo, background: COLOR.paperDim, borderRadius: 3 }}
                  >
                    <User size={14} /> Continue as {t}
                  </button>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------
   Error boundary
---------------------------------------------------------------- */
class PageErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Page error boundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="p-8"
          style={{
            fontFamily: FONT_BODY,
            background: COLOR.maroonSoft,
            border: `1px solid ${COLOR.maroon}`,
            borderRadius: 4,
            color: COLOR.maroon,
          }}
        >
          <p style={{ fontWeight: 600, marginBottom: 6 }}>Something went wrong on this page.</p>
          <p style={{ fontSize: 13 }}>
            Refresh the page to try again. If the problem persists, check that the backend is running on port 8000.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ---------------------------------------------------------------
   App shell
--------------------------------------------------------------- */
export default function App() {
  const [currentTeacher, setCurrentTeacher] = useState(null);
  const [teachersData, setTeachersData] = useState({});
  const [page, setPage] = useState("classroom");

  const data = currentTeacher ? teachersData[currentTeacher] || defaultTeacherData() : defaultTeacherData();

  const updateField = (field, updater) => {
    setTeachersData((prev) => {
      const current = prev[currentTeacher] || defaultTeacherData();
      const nextValue = typeof updater === "function" ? updater(current[field]) : updater;
      return { ...prev, [currentTeacher]: { ...current, [field]: nextValue } };
    });
  };

  const handleLogin = (name) => {
    setTeachersData((prev) => (prev[name] ? prev : { ...prev, [name]: defaultTeacherData() }));
    setCurrentTeacher(name);
    setPage("classroom");
  };

  const handleLogout = () => setCurrentTeacher(null);

  if (!currentTeacher) {
    return <Login knownTeachers={Object.keys(teachersData)} onLogin={handleLogin} />;
  }

  const setTextbook = (v) => updateField("textbook", v);
  const setCards = (v) => updateField("cards", v);
  const setQueue = (v) => updateField("queue", v);
  const setGlossary = (v) => updateField("glossary", v);
  const setImages = (v) => updateField("images", v);
  const setMaterial = (v) => updateField("material", v);

  const renderPage = () => {
    switch (page) {
      case "classroom": return <LiveClassroom textbook={data.textbook} teacher={currentTeacher} images={data.images} />;
      case "content": return <ContentLibrary textbook={data.textbook} setTextbook={setTextbook} images={data.images} setImages={setImages} material={data.material} setMaterial={setMaterial} setCards={setCards} setQueue={setQueue} />;
      case "flashcards": return <Flashcards cards={data.cards} setCards={setCards} queue={data.queue} setQueue={setQueue} textbook={data.textbook} />;
      case "misconceptions": return <Misconceptions cards={data.cards} />;
      case "worksheets": return <Worksheets textbook={data.textbook} worksheet={data.material.worksheet} />;
      case "dictionary": return <Dictionary textbook={data.textbook} />;
      default: return null;
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: COLOR.paper, fontFamily: FONT_BODY }}>
      <FontImport />
      <div className="flex">
        {/* Sidebar */}
        <div style={{ width: 220, background: COLOR.indigo, minHeight: "100vh" }} className="flex-shrink-0 py-6 px-3 flex flex-col">
          <div className="px-3 mb-8">
            <p style={{ fontFamily: FONT_HEAD, color: "#fff", fontSize: 18, fontWeight: 600 }}>GuruDhwani</p>
            <p style={{ fontFamily: FONT_BODY, color: COLOR.ochreSoft, fontSize: 11, marginTop: 2 }}>Santali classroom assistant</p>
          </div>
          <nav className="space-y-1" style={{ flex: 1 }}>
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = page === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => setPage(item.key)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-left"
                  style={{
                    fontFamily: FONT_BODY,
                    borderRadius: 3,
                    color: active ? COLOR.indigo : "#E7E1D0",
                    background: active ? COLOR.ochreSoft : "transparent",
                    fontWeight: active ? 600 : 400,
                  }}
                >
                  <Icon size={16} />
                  {item.label}
                </button>
              );
            })}
          </nav>
          <div className="px-3 pt-3" style={{ borderTop: `1px solid rgba(255,255,255,0.12)` }}>
            <div className="flex items-center gap-2 mb-2">
              <User size={14} color={COLOR.ochreSoft} />
              <span style={{ fontFamily: FONT_BODY, fontSize: 13, color: "#fff", fontWeight: 600 }}>{currentTeacher}</span>
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left"
              style={{ fontFamily: FONT_BODY, color: COLOR.ochreSoft, borderRadius: 3 }}
            >
              <LogOut size={14} /> Switch teacher
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-8" style={{ maxWidth: 1180 }}>
          <PageErrorBoundary>
            {renderPage()}
          </PageErrorBoundary>
        </div>
      </div>
    </div>
  );
}
