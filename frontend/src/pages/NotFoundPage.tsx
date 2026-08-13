import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="page-placeholder">
      <p className="eyebrow">404</p>
      <h1>Página no encontrada</h1>
      <p>La página solicitada no existe.</p>
      <Link to="/inicio">Volver a Inicio</Link>
    </section>
  );
}
