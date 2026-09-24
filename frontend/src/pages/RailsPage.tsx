import { useEffect, useState } from "react";
import { api } from "../api/client";
type R = { id: number; store_id: number; label: string; length_cm: number };
export default function RailsPage() {
  const [rows, setRows] = useState<R[]>([]);
  const [draft, setDraft] = useState<Record<number, string>>({});
  const [errs, setErrs] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const reload = () => api<R[]>("/rails").then(rs => { setRows(rs); setDraft({}); });
  useEffect(() => { reload(); }, []);
  async function save(r: R) {
    const text = (draft[r.id] ?? String(r.length_cm)).trim();
    const next = Number(text);
    if (!text || !Number.isFinite(next) || next <= 0) {
      setErrs(m => ({ ...m, [r.id]: "请输入大于 0 的厘米数" }));
      return;
    }
    setMsg(""); setErrs(m => ({ ...m, [r.id]: "" })); setBusy(r.id);
    try {
      const updated = await api<R>(`/rails/${r.id}`, { method: "PATCH", body: JSON.stringify({ length_cm: next }) });
      setMsg(`${r.label} 杆长已更新为 ${updated.length_cm} cm`);
      await reload();
    } catch (e) {
      setErrs(m => ({ ...m, [r.id]: e instanceof Error ? e.message : String(e) }));
    } finally {
      setBusy(null);
    }
  }
  return (<>
    <h2>挂杆</h2>
    {msg && <div className="ok">{msg}</div>}
    <table className="table"><thead><tr><th>标签</th><th>门店</th><th>长度 cm</th><th>新长度 cm</th><th></th></tr></thead>
    <tbody>{rows.map(r => <tr key={r.id}>
      <td>{r.label}</td><td>{r.store_id}</td><td className="mono">{r.length_cm}</td>
      <td><input type="number" min="0" step="1" style={{ width: "7em" }}
        value={draft[r.id] ?? String(r.length_cm)}
        onChange={e => setDraft(m => ({ ...m, [r.id]: e.target.value }))}
        onKeyDown={e => { if (e.key === "Enter") save(r); }}
        disabled={busy === r.id} /></td>
      <td><button onClick={() => save(r)} disabled={busy === r.id}>{busy === r.id ? "保存中…" : "保存"}</button>
        {errs[r.id] && <div className="err">{errs[r.id]}</div>}</td>
    </tr>)}</tbody></table>
  </>);
}
