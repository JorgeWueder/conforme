import { Suspense } from "react";
import { InicioCargando, SesionProvider } from "../src/sesion";
import "../src/estilos.css";
import "../src/marco.css";
import "../src/evaluacion/evaluacion.css";
import "../src/documentos/documentos.css";

export const metadata = {
  title: { default: "Conforme", template: "%s | Conforme" },
  description: "Evaluación de proveedores y seguimiento de compras públicas en la Universidad Nacional de Trujillo.",
};

export default function Layout({ children }) {
  return <html lang="es-PE"><body>
    <SesionProvider>
      <Suspense fallback={<InicioCargando />}>{children}</Suspense>
    </SesionProvider>
  </body></html>;
}
