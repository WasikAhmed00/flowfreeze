export type Incident = {
  incident_id: string;
  scenario_id: string;
  reported_transaction_id: string;
  reported_at: string;
  analysis_at?: string;
  reported_amount: string | number;
  incident_type: string;
  scenario_type: string;
  status: string;
  case_status?: string;
  assigned_analyst?: string;
  urgency?: string;
  created_time?: string;
  last_updated_time?: string;
  priority?: string;
  risk_score?: number | null;
  potentially_exposed_value?: string | number | null;
  predicted_next_move?: string;
};

export type WalletTaint = {
  wallet_id: string;
  customer_type: string;
  balance_bdt: string | number;
  potentially_tainted_bdt: string | number;
  potentially_legitimate_bdt: string | number;
  potentially_tainted_ratio: string | number;
};

export type WalletRecommendation = {
  wallet_id: string;
  risk_score: number | null;
  next_move_probabilities: Record<string, number> | null;
  balance_bdt: string | number;
  potentially_tainted_bdt: string | number;
  potentially_legitimate_bdt: string | number;
  proposed_simulated_hold_bdt: string | number;
  estimated_legitimate_value_affected_bdt: string | number;
  urgency: string;
  action: string;
  reasons: string[];
  evidence_transaction_ids: string[];
  fraud_intelligence_score?: number;
  expected_risk_reduction_points?: number;
  recommendation_reasons?: string[];
};

export type Analysis = {
  scenario_id: string;
  incident: Incident;
  as_of: string;
  synthetic: boolean;
  model_predictions: Record<string, unknown>;
  replay: Record<string, unknown>;
  trace: Record<string, any>;
  taint: Record<string, any> & { wallets: WalletTaint[]; movements: Record<string, any>[] };
  recommendation: Record<string, any> & { recommendations: WalletRecommendation[] };
  intelligence?: { method: string; wallets: Record<string, { fraud_score: number; components: Record<string, number>; graph_explanation: string[]; prediction: Record<string, any> }> };
};

export type Metrics = {
  synthetic: boolean;
  dataset?: { incident_count: number; transaction_count: number; wallet_count: number };
  audit?: { decision_count: number; decision_counts: Record<string, number> };
  simulations?: {
    count: number;
    estimated_tainted_value_preserved_bdt: string;
    estimated_legitimate_value_affected_bdt: string;
  };
  ml_evaluation?: Record<string, any>;
  real_public_model?: {
    available: boolean;
    synthetic: boolean;
    metadata?: { rows_loaded?: number; model_type?: string; evaluation_metrics?: Record<string, any> } | null;
    warning?: string;
  };
  end_to_end_evaluation?: { metrics_available: boolean; results?: Record<string, any> | null; warning?: string };
  financial_impact?: { metrics_available: boolean; synthetic_data: boolean; results?: Record<string, any> | null; warning?: string };
  warning?: string;
};

export type ImpactStrategy = {
  wallets_identified: number;
  downstream_wallets_identified: number;
  downstream_hops_identified: number;
  maximum_downstream_depth: number;
  potentially_tainted_value_identified_bdt: string;
  remaining_potentially_tainted_value_bdt: string;
  already_cashed_out_potentially_tainted_value_bdt: string;
  cashouts_identified: number;
  unique_transaction_value_examined_bdt: string;
  potentially_legitimate_value_at_risk_bdt: string;
};

export type ImpactPath = {
  wallet_ids: string[];
  terminal_cashout: boolean;
  edges: Array<{
    transaction_id: string;
    from_wallet: string;
    to_wallet: string;
    gross_amount_bdt: string | number;
    potentially_tainted_bdt: string;
    transaction_type: string;
    cashout: boolean;
  }>;
};

export type ImpactCase = {
  synthetic: boolean;
  scenario_id: string;
  incident_id: string;
  as_of: string;
  source_wallet_id: string;
  direct_recipient_wallet_id: string;
  reported_amount_bdt: string;
  total_potentially_exposed_value_bdt: string;
  remaining_potentially_tainted_value_bdt: string;
  already_cashed_out_potentially_tainted_value_bdt: string;
  comparison: {
    direct_recipient_only: ImpactStrategy;
    flowfreeze_multi_hop: ImpactStrategy;
    missed_exposure_bdt: string;
    additional_exposure_identified_by_multi_hop_bdt: string;
    exposure_recovery_rate: number;
    direct_only_coverage_of_traced_exposure_rate: number;
  };
  graph: {
    trace_window_minutes: number;
    hop_limit: number;
    truncated: boolean;
    downstream_wallet_ids: string[];
    downstream_unique_gross_transaction_value_bdt: string;
    representative_paths: ImpactPath[];
  };
  response_delay_curve: Array<{
    delay_minutes: number;
    as_of: string;
    cumulative_downstream_transaction_value_bdt: string;
    cumulative_potentially_tainted_value_bdt: string;
    downstream_wallets_identified: number;
    maximum_downstream_hops_identified: number;
    cashout_events_before_intervention: number;
    estimated_exposure_remaining_bdt: string;
    estimated_exposure_already_cashed_out_bdt: string;
    estimated_total_potentially_exposed_bdt: string;
    synthetic: boolean;
    comparison?: {
      direct_recipient_only: ImpactStrategy;
      flowfreeze_multi_hop: ImpactStrategy;
      missed_exposure_bdt: string;
    };
    representative_paths?: ImpactPath[];
    trace_truncated?: boolean;
  }>;
};

export type DecisionRecord = {
  decision_id: number;
  incident_id: string;
  scenario_id: string;
  wallet_id: string;
  decision: 'approve' | 'reject' | 'modify';
  proposed_amount_bdt: string;
  reason: string;
  actor: string;
  created_at: string;
  synthetic: boolean;
};
