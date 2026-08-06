interface PagePlaceholderProps {
  title: string;
  description: string;
}

export function PagePlaceholder({ title, description }: PagePlaceholderProps) {
  return (
    <section className="page-placeholder">
      <p className="eyebrow">LifeManager V1</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </section>
  );
}
