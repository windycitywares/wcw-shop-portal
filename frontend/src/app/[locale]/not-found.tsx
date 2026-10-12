"use client";

import { useI18n } from "@/i18n/client";
import { ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/misc";

export default function NotFound() {
  const { t, href } = useI18n();
  return (
    <Container className="py-28 text-center">
      <p className="text-sm text-muted">{t.notFound.eyebrow}</p>
      <h1 className="mx-auto mt-3 max-w-xl text-5xl">{t.notFound.title}</h1>
      <p className="mt-4 text-muted">{t.notFound.text}</p>
      <ButtonLink href={href("/shop")} className="mt-8">
        {t.notFound.cta}
      </ButtonLink>
    </Container>
  );
}
