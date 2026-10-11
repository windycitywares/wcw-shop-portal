import { ButtonLink } from "@/components/ui/Button";
import { Container } from "@/components/ui/misc";

export default function NotFound() {
  return (
    <Container className="py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-accent">404</p>
      <h1 className="mt-3 text-5xl">We couldn’t find that page</h1>
      <p className="mt-4 text-muted">It may have moved, or the product is no longer available.</p>
      <ButtonLink href="/shop" className="mt-8">
        Browse the shop
      </ButtonLink>
    </Container>
  );
}
