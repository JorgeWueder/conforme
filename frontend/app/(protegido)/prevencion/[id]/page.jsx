import { notFound } from "next/navigation";
import { FichaPrevencion } from "../../../../src/prevencion/ficha";

export default async function Revision({ params }) {
  const { id } = await params;
  if (!/^[1-9]\d{0,18}$/.test(id)) notFound();
  return <FichaPrevencion id={id} />;
}
