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
  end_to_end_evaluation?: { metrics_available: boolean; results?: Record<string, any> | null; warning?: string };
  warning?: string;
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
