"use strict";
const $ = (id) => document.getElementById(id);
let session, selected = "maya", current = null, busy = false, viewRevision = 0;
const verdicts = new Set(["ALLOW", "REVIEW", "BLOCK", "HUMAN_DECISION"]);
function node(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text;
  if (className) item.className = className;
  return item;
}
function showError(error) {
  $("error").textContent = error.message || "The local request failed. Check the saved history before retrying.";
  $("error").hidden = false;
}
function setBusy(value) {
  busy = value;
  $("run-button").disabled = value;
  $("refresh-history").disabled = value;
  document.querySelectorAll(".case-button, .history-row button, #decision-form input, #decision-form textarea").forEach(el => { el.disabled = value; });
  updateSave();
}
function updateSave() {
  const chosen = document.querySelector('input[name="option"]:checked');
  $("save-button").disabled = busy || !current || !!current.decision || !chosen || !$("actor").value.trim() || !$("reason").value.trim() || !$("ack").checked;
}
async function api(path, body) {
  const options = body === undefined ? {} : {method:"POST", headers:{"Content-Type":"application/json", "X-Review-Token":session.token}, body:JSON.stringify(body)};
  const response = await fetch(path, {...options, cache:"no-store", credentials:"omit"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Local request failed.");
  return data;
}
function selectCase(id) {
  if (busy) return;
  selected = id; current = null; viewRevision++;
  const entry = session.cases.find(c => c.id === id);
  $("case-title").textContent = entry.name;
  $("case-detail").textContent = entry.detail;
  $("result").hidden = true; $("empty").hidden = false; $("error").hidden = true;
  $("decision-form").reset();
  $("status").textContent = "Ready. Run a fresh verification for this case.";
  document.querySelectorAll(".case-button").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.case === id)));
  updateSave();
}
function renderCases() {
  session.cases.forEach((entry, index) => {
    const button = node("button", undefined, "case-button");
    button.type = "button"; button.dataset.case = entry.id;
    button.setAttribute("aria-pressed", String(entry.id === selected));
    button.append(node("div", String(index + 1).padStart(2, "0"), "case-number"), node("strong", entry.name), node("span", entry.detail));
    button.addEventListener("click", () => selectCase(entry.id));
    $("case-list").append(button);
  });
}
function renderReceipt(receipt) {
  const target = $("receipt"); target.replaceChildren();
  target.append(node("h3", "Decision recorded. Evidence unchanged."));
  const list = node("dl");
  const fields = [
    ["Selected intent", receipt.selected_option.label],
    ["Reason", receipt.reason],
    ["Reviewer (self-reported; not authenticated)", receipt.actor_display_name],
    ["Recorded at (UTC)", receipt.recorded_at],
    ["Original verdict / claim state", `${receipt.original_verdict} / ${receipt.original_claim_state}`],
    ["Decision ID", receipt.decision_id],
    ["Bound certificate checksum", receipt.certificate_sha256],
    ["Receipt checksum", receipt.checksum]
  ];
  fields.forEach(([label, value]) => list.append(node("dt", label), node("dd", value)));
  target.append(list, node("p", "Intent only. No action was executed, no result authorized, and no original evidence changed. Checksums are not authenticated signatures.", "small"));
}
function renderRun(run) {
  current = run;
  const cert = run.certificate, card = cert.verdict_card;
  if (!run.certificate_integrity_valid || !verdicts.has(card.verdict)) throw new Error("An integrity-valid result is required.");
  $("empty").hidden = true; $("result").hidden = false; $("error").hidden = true;
  $("verdict-panel").className = "verdict-card " + card.verdict.toLowerCase();
  $("verdict").textContent = card.verdict.replaceAll("_", " ");
  $("rule").textContent = card.fired_rule;
  $("headline").textContent = card.headline;
  $("root-cause").textContent = card.root_cause || "";
  $("root-cause").hidden = !card.root_cause;
  $("claim-state").textContent = card.claim_state;
  $("evidence-class").textContent = card.evidence_class;
  $("physics").textContent = card.physical_interpretation;
  $("certificate-id").textContent = cert.certificate_id;
  $("checksum").textContent = cert.signature;
  $("download").href = `/api/runs/${encodeURIComponent(cert.certificate_id)}/export`;
  $("download").textContent = run.decision ? "Download certificate + decision ↓" : "Download review JSON ↓";
  $("numbers").replaceChildren();
  // Display only values emitted by the verifier, with no UI verdict arithmetic.
  Object.entries(card.numbers).forEach(([key, value]) => {
    const metric = node("dl", undefined, "number-card");
    metric.append(node("dt", key.replaceAll("_", " ")), node("dd", Number.isInteger(value) ? String(value) : value.toFixed(4)));
    $("numbers").append(metric);
  });
  $("trace").replaceChildren();
  (cert.trace?.steps || []).forEach(step => {
    const row = node("li");
    row.append(node("strong", step.tool.replaceAll("_", " ")), node("span", `${step.outcome} · ${step.duration_ms.toFixed(1)} ms`));
    $("trace").append(row);
  });
  if (!cert.trace?.steps?.length) $("trace").append(node("li", "No execution trace recorded."));
  $("findings").replaceChildren();
  card.findings.forEach(finding => $("findings").append(node("li", `${finding.severity}: ${finding.summary} ${finding.detail || ""}`)));
  $("limitations").replaceChildren();
  cert.limitations.forEach(item => $("limitations").append(node("li", item)));
  const escalation = card.escalation;
  $("decision-form").reset();
  $("options").replaceChildren(node("legend", "Your selected next action"));
  $("decision-title").textContent = escalation ? "One question for you." : "No decision required.";
  $("question").textContent = escalation?.question || "";
  $("context").textContent = escalation?.context || "";
  $("context").hidden = !escalation;
  $("no-decision").hidden = !!escalation;
  $("receipt").hidden = !run.decision;
  $("decision-form").hidden = !escalation || !!run.decision;
  $("preference-note").textContent = card.verdict === "HUMAN_DECISION" ? "No agent preference. No option is preselected." : "";
  if (escalation) escalation.options.forEach(option => {
    const label = node("label", undefined, "option");
    const input = node("input"); input.type = "radio"; input.name = "option"; input.value = option.option_id; input.required = true;
    const text = node("span");
    const policyNote = escalation.recommended_option_id === option.option_id ? " · Policy recommendation" : "";
    text.append(node("strong", option.label + policyNote), node("small", option.consequence));
    label.append(input, text); $("options").append(label);
  });
  if (run.decision) renderReceipt(run.decision);
  $("status").textContent = run.decision ? "Saved local record loaded. Original certificate integrity verified." : "Verification complete. Certificate retained locally; no model called.";
  updateSave();
}
async function loadHistory() {
  const data = await api("/api/runs");
  $("history-list").replaceChildren();
  if (!data.runs.length) $("history-list").append(node("p", "No saved runs yet. Your first verification will appear here.", "small muted"));
  data.runs.forEach(run => {
    const row = node("div", undefined, "history-row"), text = node("div");
    const caseName = session.cases.find(c => c.id === run.case)?.name || run.case;
    text.append(node("strong", `${caseName} / ${run.verdict.replaceAll("_", " ")}`));
    const state = run.decision_id ? "Decision recorded" : run.needs_decision ? "Awaiting human intent" : "No decision required";
    text.append(node("p", `${state} · ${run.issued_at} (UTC)`), node("code", run.certificate_id));
    const button = node("button", "Open record", "secondary"); button.type = "button"; button.disabled = busy;
    button.setAttribute("aria-label", `Open record ${run.certificate_id}`);
    button.addEventListener("click", async () => {
      if (busy) return;
      selectCase(run.case); const revision = viewRevision; setBusy(true);
      try { const result = await api(`/api/runs/${encodeURIComponent(run.certificate_id)}`); if (revision === viewRevision) renderRun(result); $("case-title").scrollIntoView({block:"start"}); }
      catch (error) { showError(error); }
      finally { setBusy(false); }
    });
    row.append(text, button); $("history-list").append(row);
  });
}
$("run-button").addEventListener("click", async () => {
  if (busy || !session) return;
  selectCase(selected); setBusy(true); $("status").textContent = "Inspecting the synthetic package and running deterministic verification…";
  try { renderRun(await api("/api/runs", {case:selected})); await loadHistory(); }
  catch (error) { showError(error); $("status").textContent = "No new result displayed. Check history before retrying."; }
  finally { setBusy(false); }
});
$("decision-form").addEventListener("input", updateSave);
$("decision-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy || $("save-button").disabled || !current) return;
  const certificate = current.certificate;
  const payload = {certificate_sha256:certificate.signature, option_id:document.querySelector('input[name="option"]:checked').value, actor_display_name:$("actor").value.trim(), reason:$("reason").value.trim()};
  setBusy(true); $("error").hidden = true; $("status").textContent = "Saving a separate local decision receipt…";
  try { renderRun(await api(`/api/runs/${encodeURIComponent(certificate.certificate_id)}/decision`, payload)); await loadHistory(); }
  catch (error) { showError(error); $("status").textContent = "Save not confirmed. Refresh history before retrying; identical retries are safe."; }
  finally { setBusy(false); }
});
$("refresh-history").addEventListener("click", async () => {
  if (busy) return; setBusy(true);
  try { await loadHistory(); } catch (error) { showError(error); } finally { setBusy(false); }
});
(async function initialize() {
  setBusy(true);
  try { session = await api("/api/session"); renderCases(); await loadHistory(); }
  catch (error) { showError(error); $("status").textContent = "Workbench unavailable. Reload after the local server is ready."; }
  finally { setBusy(false); if (!session) $("run-button").disabled = true; }
})();
