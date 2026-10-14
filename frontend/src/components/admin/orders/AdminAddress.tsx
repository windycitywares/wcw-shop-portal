import { countryName } from "@/lib/account";
import type { OrderAddress } from "@/lib/types";

/** A postal address as lines of text. */
export function AdminAddress({ address }: { address: OrderAddress }) {
  return (
    <address className="not-italic leading-relaxed">
      <span className="font-medium">{address.full_name}</span>
      <br />
      {address.company && (
        <>
          {address.company}
          <br />
        </>
      )}
      {address.line1}
      {address.line2 && <>, {address.line2}</>}
      <br />
      {address.city}
      {address.region && <>, {address.region}</>} {address.postal_code}
      <br />
      {countryName(address.country, "en")}
      {address.phone && (
        <>
          <br />
          {address.phone}
        </>
      )}
    </address>
  );
}
