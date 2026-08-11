import type { ReactNode } from "react";

/**
 * One section, on one ground.
 *
 * The design alternates two grounds by section, and the ground is a property
 * of the band rather than of anything inside it — `data-ground="alt"`
 * re-points the entire palette, so a card, an accent or a hairline written once
 * renders correctly on either. That is the whole reason the tokens are built
 * the way they are: nothing in a section needs to know which ground it is
 * standing on.
 *
 * The prop says `page` or `alt`, not `ink` or `paper`, because which colour
 * each of those is depends on the theme: dark is ink with paper bands and
 * light is the reverse. A section asks to be on the other ground; it does not
 * get to know what colour that is.
 *
 * The eyebrow is numbered because the source design numbers them, and the
 * number is a position in a sequence a reader is walking rather than a count
 * of anything — so it is written here rather than derived.
 */

interface Props {
  id?: string;
  ground?: "page" | "alt";
  eyebrow?: string;
  heading: string;
  lede?: ReactNode;
  children?: ReactNode;
  /** Full-bleed content, outside the measured column. */
  bleed?: ReactNode;
}

export function Band({ id, ground = "page", eyebrow, heading, lede, children, bleed }: Props) {
  return (
    <section
      id={id}
      className="b-band"
      {...(ground === "alt" ? { "data-ground": "alt" } : {})}
    >
      <div className="b-measure">
        {eyebrow && <p className="b-eyebrow mb-6 text-b-src">{eyebrow}</p>}
        <h2 className="b-h2 max-w-[22ch]">{heading}</h2>
        {lede && <p className="b-lede mt-5 max-w-[58ch]">{lede}</p>}
        {children && <div className="mt-10">{children}</div>}
      </div>
      {bleed}
    </section>
  );
}
