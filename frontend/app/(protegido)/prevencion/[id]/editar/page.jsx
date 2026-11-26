import { notFound } from "next/navigation";
import { EditarPrevencion } from "../../../../../src/prevencion/formulario";

export default async function EditarRevision({ params }) {
  const { id } = await params;
  if (!/^[1-9]\d{0,18}$/.test(id)) notFound();
  return <EditarPrevencion id={id} />;
}
