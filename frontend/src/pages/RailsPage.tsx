import { useEffect, useState } from "react";
import { api } from "../api/client";
type R = { id: number; store_id: number; label: string; length_cm: number };
export default function RailsPage() {
  const [rows, setRows] = useState<R[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const reload = () => api<R[]>("/rails").then(setRows);
  useEffect(() => { reload(); }, []);
  function startEdit(r: R) {
    setEditing(r.id);
    setDraft(String(r.length_cm));
    setMsg(""); setErr("");
  }
  function cancelEdit() {
    setEditing(null);
    setDraft("");
    setErr("");
  }
  async function save(id: number) {
    const next = Number(draft);
    if (!Number.isFinite(next) || next <= 0) {
      setErr("请输入大于 0 的杆长（厘米）");
      return;
    }
    setSaving(true);
    setMsg(""); setErr("");
    try {
      const r = await api<R>(`/rails/${id}`, { method: "PATCH", body: JSON.stringify({ length_cm: next }) });
      setMsg(`${r.label} 杆长已更新为 ${r.length_cm}cm`);
      setEditing(null);
      setDraft("");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }
  return (<>
    <h2>挂杆</h2>
    {msg && <div className="ok">{msg}</div>}
    {err && <div className="err">{err}</div>}
    <table className="table"><thead><tr><th>标签</th><th>门店</th><th>长度 cm</th><th></th></tr></thead>
    <tbody>{rows.map(r => <tr key={r.id}>
      <td>{r.label}</td><td>{r.store_id}</td>
      <td className="mono">{editing === r.id
        ? <input value={draft} inputMode="decimal" style={{ width: "7rem" }}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") save(r.id); if (e.key === "Escape") cancelEdit(); }}
            autoFocus />
        : <>{r.length_cm}</>}</td>
      <td>{editing === r.id
        ? <><button disabled={saving} onClick={() => save(r.id)}>保存</button>{" "}
            <button onClick={cancelEdit} style={{ background: "var(--panel)", color: "var(--text)" }}>取消</button></>
        : <button onClick={() => startEdit(r)} style={{ background: "var(--panel)", color: "var(--text)" }}>修改杆长</button>}
      </td>
    </tr>)}</tbody></table>
  </>);
}
