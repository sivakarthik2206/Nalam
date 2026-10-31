import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import api from "./api";
import {
  AdminDashboardResponse,
  AdherenceLogResponse,
  AdherenceScoreResponse,
  DailyAdherenceResponse,
  FamilyDashboard,
  ManualCallResponse,
  MedicationCreate,
  MedicationResponse,
  MedicationUpdate,
  PaginatedResponse,
  PatientCreate,
  PatientResponse,
  PatientUpdate,
  PatientWithMedications,
  PatientSummary,
  RefillInfo,
  TrendPoint,
  AlertResponse,
} from "./types";

// ============================================================================
// Patients
// ============================================================================

export function usePatients(filters?: {
  pharmacy_id?: string;
  language?: string;
  page?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["patients", filters],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<PatientResponse>>("/patients/", {
        params: filters,
      });
      return data;
    },
  });
}

export function usePatient(id: string) {
  return useQuery({
    queryKey: ["patient", id],
    queryFn: async () => {
      const { data } = await api.get<PatientWithMedications>(`/patients/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useCreatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: PatientCreate) => {
      const { data } = await api.post<PatientResponse>("/patients/", payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    },
  });
}

export function useUpdatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: PatientUpdate }) => {
      const { data } = await api.put<PatientResponse>(`/patients/${id}`, payload);
      return data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["patient", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    },
  });
}

// ============================================================================
// Medications
// ============================================================================

export function usePatientMedications(patientId: string) {
  return useQuery({
    queryKey: ["patient-medications", patientId],
    queryFn: async () => {
      const { data } = await api.get<MedicationResponse[]>(
        `/patients/${patientId}/medications`
      );
      return data;
    },
    enabled: !!patientId,
  });
}

export function useAddMedication(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: MedicationCreate) => {
      const { data } = await api.post<MedicationResponse>(
        `/patients/${patientId}/medications`,
        payload
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient", patientId] });
      queryClient.invalidateQueries({ queryKey: ["patient-medications", patientId] });
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    },
  });
}

export function useUpdateMedication(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      medicationId,
      payload,
    }: {
      medicationId: string;
      payload: MedicationUpdate;
    }) => {
      const { data } = await api.put<MedicationResponse>(
        `/patients/${patientId}/medications/${medicationId}`,
        payload
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient", patientId] });
      queryClient.invalidateQueries({ queryKey: ["patient-medications", patientId] });
    },
  });
}

export function useDeactivateMedication(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (medicationId: string) => {
      await api.delete(`/patients/${patientId}/medications/${medicationId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient", patientId] });
      queryClient.invalidateQueries({ queryKey: ["patient-medications", patientId] });
    },
  });
}

// ============================================================================
// Adherence
// ============================================================================

export function useAdherenceScore(patientId: string, days: number = 7) {
  return useQuery({
    queryKey: ["adherence-score", patientId, days],
    queryFn: async () => {
      const { data } = await api.get<AdherenceScoreResponse>(
        `/adherence/${patientId}/score`,
        { params: { days } }
      );
      return data;
    },
    enabled: !!patientId,
  });
}

export function useAdherenceHistory(
  patientId: string,
  days: number = 7,
  medicationId?: string
) {
  return useQuery({
    queryKey: ["adherence-history", patientId, days, medicationId],
    queryFn: async () => {
      const { data } = await api.get<AdherenceLogResponse[]>(
        `/adherence/${patientId}/history`,
        { params: { days, medication_id: medicationId } }
      );
      return data;
    },
    enabled: !!patientId,
  });
}

export function useAdherenceTrend(patientId: string, days: number = 30) {
  return useQuery({
    queryKey: ["adherence-trend", patientId, days],
    queryFn: async () => {
      const { data } = await api.get<TrendPoint[]>(
        `/adherence/${patientId}/trend`,
        { params: { days } }
      );
      return data;
    },
    enabled: !!patientId,
  });
}

export function useDailyStatus(patientId: string) {
  return useQuery({
    queryKey: ["adherence-daily", patientId],
    queryFn: async () => {
      const { data } = await api.get<DailyAdherenceResponse>(
        `/adherence/${patientId}/daily`
      );
      return data;
    },
    enabled: !!patientId,
  });
}

// ============================================================================
// Dashboards
// ============================================================================

export function useAdminDashboard(pharmacyId?: string) {
  return useQuery({
    queryKey: ["admin-dashboard", pharmacyId],
    queryFn: async () => {
      const { data } = await api.get<AdminDashboardResponse>("/dashboard/admin", {
        params: pharmacyId ? { pharmacy_id: pharmacyId } : undefined,
      });
      return data;
    },
    refetchInterval: 60000, // 60s live refresh
  });
}

export function useFamilyDashboard(patientId: string) {
  return useQuery({
    queryKey: ["family-dashboard", patientId],
    queryFn: async () => {
      const { data } = await api.get<FamilyDashboard>(
        `/dashboard/family/${patientId}`
      );
      return data;
    },
    enabled: !!patientId,
    refetchInterval: 60000,
  });
}

// ============================================================================
// Alerts
// ============================================================================

export function useAlerts(filters?: {
  patient_id?: string;
  severity?: string;
  is_read?: boolean;
  page?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["alerts", filters],
    queryFn: async () => {
      const { data } = await api.get<PaginatedResponse<AlertResponse>>(
        "/dashboard/alerts",
        { params: filters }
      );
      return data;
    },
    refetchInterval: 30000,
  });
}

export function useMarkAlertRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (alertId: string) => {
      const { data } = await api.put<AlertResponse>(
        `/dashboard/alerts/${alertId}/read`
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
    },
  });
}

// ============================================================================
// Refills
// ============================================================================

export function useRefillPredictions() {
  return useQuery({
    queryKey: ["refills"],
    queryFn: async () => {
      const { data } = await api.get<RefillInfo[]>("/dashboard/refills");
      return data;
    },
    refetchInterval: 60000,
  });
}

// ============================================================================
// Patient Summary
// ============================================================================

export function usePatientSummary(patientId: string) {
  return useQuery({
    queryKey: ['patient-summary', patientId],
    queryFn: () => api.get<PatientSummary>(`/patient-summary?patient_id=${patientId}`).then(r => r.data),
    enabled: !!patientId,
    refetchInterval: 60_000,
  });
}

export function useAllPatientSummaries() {
  return useQuery({
    queryKey: ['patient-summary-all'],
    queryFn: () => api.get<PatientSummary[]>('/patient-summary').then(r => r.data),
    refetchInterval: 30_000,
  });
}

// ============================================================================
// Trigger Call
// ============================================================================

export function useTriggerCall(patientId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (medicationId?: string) => {
      const { data } = await api.post<ManualCallResponse>(
        `/dashboard/trigger-call/${patientId}`,
        null,
        { params: medicationId ? { medication_id: medicationId } : undefined }
      );
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patient", patientId] });
      queryClient.invalidateQueries({ queryKey: ["admin-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["adherence-history", patientId] });
    },
  });
}
