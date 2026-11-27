import { SoloEvaluacion } from "../../../src/evaluacion/permiso";

export const metadata = { title: "Revisión documental" };

export default function LayoutDocumentos({ children }) {
  return <SoloEvaluacion>{children}</SoloEvaluacion>;
}
