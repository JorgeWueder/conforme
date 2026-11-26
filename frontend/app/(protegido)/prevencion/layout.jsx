import { SoloAbastecimiento } from "../../../src/prevencion/permiso";

export const metadata = { title: "Revisión previa" };

export default function LayoutPrevencion({ children }) {
  return <SoloAbastecimiento>{children}</SoloAbastecimiento>;
}
