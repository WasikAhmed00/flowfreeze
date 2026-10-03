const names = { cashout: 'Cash out', forward: 'Forward', no_movement: 'No movement' }

export default function PredictionBars({ probabilities, fraudRisk, source }) {
  const label = source === 'trained_synthetic_models' ? 'Synthetic model output' : source === 'user_supplied_illustrative_inputs' ? 'Illustrative input' : 'Unavailable'
  return <div className="prediction-area">
    <div className="risk-score-box"><span>FRAUD RISK</span>{fraudRisk == null ? <><b className="unavailable-score">N/A</b><small>Model not connected</small></> : <><b>{Math.round(fraudRisk * 100)}<small>%</small></b><div className="risk-meter"><i style={{ width: `${Math.max(0, Math.min(100, fraudRisk * 100))}%` }} /></div><small>{label}</small></>}</div>
    <div className="move-score-box"><span>LIKELY NEXT STEP · WITHIN 5 MIN</span>{!probabilities ? <div className="unavailable-banner"><span>—</span><div><b>No model output available</b><small>Predicted movement is unknown. This is not a zero probability.</small></div></div> : <><small>{label}</small><div className="prediction-list">{Object.entries(probabilities).map(([key, value]) => <div className="prediction-row" key={key}><span>{names[key] || key}</span><div className="prediction-track"><i className={`prediction-${key}`} style={{ width: `${Number(value) * 100}%` }} /></div><b>{Math.round(Number(value) * 100)}%</b></div>)}</div></>}</div>
  </div>
}
