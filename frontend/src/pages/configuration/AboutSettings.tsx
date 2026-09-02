export function AboutSettings() {
  return <section className="configuration-panel" aria-labelledby="about-heading">
    <h2 id="about-heading">Acerca de</h2>
    <dl className="configuration-about">
      <div><dt>Aplicación</dt><dd>LifeManager</dd></div>
      <div><dt>Versión</dt><dd>2.0.0 (en desarrollo)</dd></div>
      <div><dt>Idioma</dt><dd>Español</dd></div>
      <div><dt>Formato de fecha</dt><dd>dd/mm/yyyy</dd></div>
      <div><dt>Inicio de semana</dt><dd>Lunes</dd></div>
    </dl>
  </section>;
}
