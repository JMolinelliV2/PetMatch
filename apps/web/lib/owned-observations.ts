export type OwnedObservation = {
  id: string;
  public_id: string;
  species: string;
  sex: string;
  primary_color: string;
  size: string;
  description: string;
  description_format?: string;
  source_type: string;
  observed_at: string;
  public_location: string | null;
  latitude: number | null;
  longitude: number | null;
  location_accuracy_meters: number | null;
  share_contact: boolean;
  linked_case_id: string | null;
};

export function observationEditHref(id: string) {
  return `/mis-avisos/avistamientos/${encodeURIComponent(id)}/editar`;
}
