import Link from "next/link";

export default function NoEncontrada() {
  return <main className="contenido contenido-publico">
    <h1>Página no encontrada</h1>
    <Link href="/">Volver al inicio</Link>
  </main>;
}
