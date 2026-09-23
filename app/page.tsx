import { IconMark, IconBulb, IconFlask, IconChart, IconGlobe, IconMask } from "./icons";
import type { Edition } from "./types";
import { DsaSection } from "./Interactive";

import { getTodaysEdition } from "./getEdition";
const categoryIcons: Record<string, React.ReactNode> = {
  "TRADING": <IconChart />,
  "ANIME & MANGA": <IconMask />,
  "SOFTWARE DEV": <IconGlobe />,
};


export default async function Page() {
  const data: Edition = await getTodaysEdition();

  return (
    <div className="wrap">
      <div className="mark"><IconMark /></div>
      <h1>The Daily Loop</h1>

      <div className="tag">LEAD STORY — {data.lead.topic}</div>
      {data.lead.paragraphs.map((p, i) => (
        <p key={i}>{p}</p>
      ))}

      <div className="briefs">
  {data.briefs.map((b) => (
    <div className="story" key={b.headline}>
      <div className="tag">{categoryIcons[b.category]} {b.category}</div>
      <h3>{b.headline}</h3>
      <p>{b.body}</p>
    </div>
  ))}
</div>

     <div className="eli5">
  <div className="tag tag-orange"><IconBulb /> EXPLAIN LIKE I'M 5</div>
  <p>{data.explainli5.title}</p>
  <p>{data.explainli5.explanation}</p>
  <div className="eli5-deep">
    <p className="eli5-deep-label">The real explanation</p>
    <p>{data.explainli5.deep_dive}</p>
  </div>
</div>

      <div className="dsa">
        <div className="tag">DSA WARM-UP</div>
        <DsaSection dsa={data.dsa} />
      </div>

      {data.paper && (
        <div className="paper">
          <div className="tag"><IconFlask /> RESEARCH SPOTLIGHT</div>
          <p className="paper-title">{data.paper.title}</p>
          <p className="paper-authors">{data.paper.authors}</p>
          <p>{data.paper.summary}</p>
          <a href={data.paper.link} target="_blank" rel="noreferrer">Read the paper &rarr;</a>
        </div>
      )}
    </div>
  );
}