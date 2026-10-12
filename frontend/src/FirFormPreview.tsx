import type { DraftResponse } from './types'
import './fir-form.css'

type Field = {
  value?: string | number | boolean | null
  text?: { en?: string | null; ta?: string | null } | null
}

type Person = {
  name?: Field
  relative_name?: Field
  dob_or_age?: Field
  nationality?: Field
  occupation?: Field
  address?: Field
  contact?: Field
  passport?: { number?: Field; date_place_of_issue?: Field }
}

type FormRecord = {
  record_id: string
  status: string
  schema_version: string
  jurisdiction: { state: string; district?: Field; police_station?: Field; ps_code?: string | null }
  fir_year?: number | null
  fir_number?: string | null
  fir_date?: string | null
  acts_sections: Array<{ act: string; section: string; description_en?: string; mapping_ambiguous?: boolean }>
  occurrence: { from_datetime?: Field; to_datetime?: Field; info_received_at_ps?: Field; gd_reference?: Field }
  information_type?: string | null
  place_of_occurrence: {
    direction_from_ps?: Field
    distance_from_ps_km?: Field
    beat_no?: Field
    address?: Field
    outside_ps_limits?: boolean
    other_ps_name?: Field
    other_district?: Field
  }
  complainant: Person
  accused: Array<{ known?: boolean; unknown?: boolean; name?: Field; alias?: Field; relative_name?: Field; physical_description?: Field; address?: Field }>
  delay_reason?: Field
  properties_involved: Array<{ category?: Field; description?: Field; estimated_value_inr?: Field }>
  total_property_value_inr?: Field
  inquest_ud_case_no?: Field
  narrative: { ta?: string | null; en?: string | null }
}

function value(field?: Field | string | number | null): string {
  if (field == null) return ''
  if (typeof field === 'string' || typeof field === 'number') return String(field)
  const shown = field.text?.en || field.text?.ta || field.value
  return shown == null ? '' : String(shown)
}

function Filled({ data, className = '' }: { data?: Field | string | number | null; className?: string }) {
  const shown = value(data)
  return <span className={`fir-filled ${shown ? '' : 'fir-unfilled'} ${className}`}>{shown || '\u00a0'}</span>
}

function Label({ en, ta }: { en: string; ta?: string }) {
  return <span className="fir-label">{en}{ta && <small lang="ta">{ta}</small>}</span>
}

function Line({ en, ta, data, className = '' }: { en: string; ta?: string; data?: Field | string | number | null; className?: string }) {
  return <div className={`fir-line ${className}`}><Label en={en} ta={ta} /><Filled data={data} /></div>
}

function Section({ number, en, ta, children, className = '' }: { number: number; en: string; ta?: string; children: React.ReactNode; className?: string }) {
  return <section className={`fir-section ${className}`}><div className="fir-section-number">{number}.</div><div className="fir-section-main"><div className="fir-section-title"><Label en={en} ta={ta} /></div>{children}</div></section>
}

function PageFooter({ recordId, page }: { recordId: string; page: string }) {
  return <footer className="fir-page-footer"><span>Machine-generated IF-1 draft · Not registered</span><span>{recordId} · {page}</span></footer>
}

function FormHeader() {
  return <header className="fir-form-header">
    <div className="fir-form-number">INTEGRATED INVESTIGATION FORM - I<br />TAMIL NADU POLICE · DRAFT</div>
    <h2>FIRST INFORMATION REPORT</h2>
    <div className="fir-tamil-title" lang="ta">முதல் தகவல் அறிக்கை</div>
    <div className="fir-law">(Under Section 173, Bharatiya Nagarik Suraksha Sanhita, 2023)</div>
    <div className="fir-registration-note">FOR OFFICER REVIEW ONLY · NO FIR NUMBER ASSIGNED BY THIS SYSTEM</div>
  </header>
}

export function FirFormPreview({ draft }: { draft: DraftResponse }) {
  const record = draft.record as unknown as FormRecord
  const acts = record.acts_sections || []
  const accused = record.accused || []
  const properties = record.properties_involved || []
  const occurrence = record.occurrence || {}
  const place = record.place_of_occurrence || {}
  const person = record.complainant || {}

  return <div className="fir-form-shell">
    <div className="fir-page fir-page-one">
      <div className="fir-draft-watermark" aria-hidden="true">DRAFT</div>
      <FormHeader />
      <Section number={1} en="District / Police Station" ta="மாவட்டம் / காவல் நிலையம்">
        <div className="fir-fields-grid fir-grid-five">
          <Line en="District" ta="மாவட்டம்" data={record.jurisdiction?.district} />
          <Line en="P.S." ta="காவல் நிலையம்" data={record.jurisdiction?.police_station} />
          <Line en="Year" ta="ஆண்டு" data={record.fir_year} />
          <Line en="FIR No." ta="மு.த.அ. எண்" data={record.fir_number} />
          <Line en="Date" ta="நாள்" data={record.fir_date} />
        </div>
      </Section>

      <Section number={2} en="Acts & Sections" ta="சட்டங்கள் மற்றும் பிரிவுகள்">
        <div className="fir-act-list">
          {Array.from({ length: Math.max(4, acts.length) }, (_, index) => {
            const act = acts[index]
            return <div className="fir-act-row" key={index}>
              <span>({['i', 'ii', 'iii', 'iv'][index] || index + 1})</span>
              <Line en="Act" ta="சட்டம்" data={act?.act?.replaceAll('_', ' ')} />
              <Line en="Sections" ta="பிரிவுகள்" data={act?.section} />
              {act?.mapping_ambiguous && <span className="fir-inline-note">Confirm mapping</span>}
            </div>
          })}
        </div>
      </Section>

      <Section number={3} en="Occurrence of Offence" ta="குற்ற நிகழ்வு">
        <div className="fir-subrow"><span>(a)</span><Line en="Date from" ta="நாள் முதல்" data={occurrence.from_datetime} /><Line en="Date to" ta="நாள் வரை" data={occurrence.to_datetime} /></div>
        <div className="fir-subrow"><span>(b)</span><Line en="Information received at P.S." ta="காவல் நிலையத்தில் தகவல் பெற்ற நேரம்" data={occurrence.info_received_at_ps} /></div>
        <div className="fir-subrow"><span>(c)</span><Line en="General Diary reference" ta="பொது நாட்குறிப்பு பதிவு" data={occurrence.gd_reference} /></div>
      </Section>

      <Section number={4} en="Type of Information" ta="தகவலின் வகை">
        <Line en="Written / Oral" ta="எழுத்து மூலம் / வாய்மொழி" data={record.information_type ? record.information_type[0].toUpperCase() + record.information_type.slice(1) : null} />
      </Section>

      <Section number={5} en="Place of Occurrence" ta="குற்ற நிகழ்விடம்">
        <div className="fir-subrow"><span>(a)</span><Line en="Direction from P.S." data={place.direction_from_ps} /><Line en="Distance (km)" data={place.distance_from_ps_km} /><Line en="Beat No." data={place.beat_no} /></div>
        <div className="fir-subrow"><span>(b)</span><Line en="Address" ta="முகவரி" data={place.address} /></div>
        <div className="fir-subrow"><span>(c)</span><Line en="Outside this P.S. limits" data={typeof place.outside_ps_limits === 'boolean' ? place.outside_ps_limits ? 'Yes' : 'No' : null} /><Line en="Other P.S." data={place.other_ps_name} /><Line en="District" data={place.other_district} /></div>
      </Section>

      <Section number={6} en="Complainant / Informant" ta="புகார்தாரர் / தகவல் அளிப்பவர்">
        <div className="fir-person-grid">
          <Line en="(a) Name" ta="பெயர்" data={person.name} />
          <Line en="(b) Father's / Husband's name" data={person.relative_name} />
          <Line en="(c) Date / year of birth" data={person.dob_or_age} />
          <Line en="(d) Nationality" data={person.nationality} />
          <Line en="(e) Passport no." data={person.passport?.number} />
          <Line en="Date / place of issue" data={person.passport?.date_place_of_issue} />
          <Line en="(f) Occupation" data={person.occupation} />
          <Line en="(g) Address" ta="முகவரி" data={person.address} />
          <Line en="Contact" data={person.contact} />
        </div>
      </Section>

      <Section number={7} en="Details of known / suspected / unknown accused" ta="குற்றம் சாட்டப்பட்டவர்களின் விவரங்கள்">
        <div className="fir-free-entry fir-free-accused">
          {accused.length ? accused.map((item, index) => <p key={index}>{index + 1}. {item.known ? 'Known' : item.unknown ? 'Unknown' : 'Suspected'} — {value(item.name) || 'Name not recorded'}{value(item.address) && `; ${value(item.address)}`}</p>) : <div className="fir-ruled-space" />}
        </div>
      </Section>

      <Section number={8} en="Reasons for delay in reporting" ta="புகார் அளிப்பதில் தாமதத்திற்கான காரணம்">
        <div className="fir-free-entry"><Filled data={record.delay_reason} className="fir-wide-value" /></div>
      </Section>
      <PageFooter recordId={record.record_id} page="Form · 1" />
    </div>

    <div className="fir-page fir-page-two">
      <div className="fir-draft-watermark" aria-hidden="true">DRAFT</div>
      <div className="fir-continuation">FIRST INFORMATION REPORT · FORM IF-I <span>CONTINUED</span></div>
      <Section number={9} en="Particulars of properties stolen / involved" ta="திருடப்பட்ட / சம்பந்தப்பட்ட சொத்துகளின் விவரம்">
        <div className="fir-free-entry fir-property-entry">
          {properties.length ? properties.map((item, index) => <p key={index}>{index + 1}. {value(item.description) || value(item.category) || 'Description pending'}{value(item.estimated_value_inr) && ` — ₹ ${value(item.estimated_value_inr)}`}</p>) : <div className="fir-ruled-space" />}
        </div>
      </Section>
      <Section number={10} en="Total value of properties stolen / involved" ta="சொத்துகளின் மொத்த மதிப்பு">
        <Line en="Value (INR)" data={record.total_property_value_inr} />
      </Section>
      <Section number={11} en="Inquest Report / Unnatural Death Case No., if any" ta="விசாரணை அறிக்கை / இயற்கைக்கு மாறான மரண வழக்கு எண்">
        <Filled data={record.inquest_ud_case_no} className="fir-wide-value" />
      </Section>
      <Section number={12} en="FIR Contents (attach separate sheet if required)" ta="முதல் தகவல் அறிக்கையின் உள்ளடக்கம்">
        <div className="fir-contents-reference">Source account and English working text attached as Annexure A. Officer must verify and enter the final FIR narrative.</div>
        <div className="fir-ruled-space fir-contents-lines" />
      </Section>

      <div className="fir-page-two-bottom">
        <Section number={13} en="Action taken" ta="எடுக்கப்பட்ட நடவடிக்கை">
          <div className="fir-action-text">Registered the case and took up investigation / directed investigation / refused investigation / transferred to P.S. on point of jurisdiction:</div>
          <div className="fir-ruled-space fir-action-lines" />
          <div className="fir-action-note">No option is selected by this system. To be completed by the officer in charge.</div>
        </Section>
        <div className="fir-acknowledgment">FIR read over to the complainant / informant; correctness acknowledged and copy provided: <span>Pending officer and informant confirmation</span></div>
        <Section number={14} en="Signature / thumb impression of complainant / informant" ta="புகார்தாரரின் கையொப்பம் / பெருவிரல் ரேகை">
          <div className="fir-signature-grid"><div className="fir-signature-line">Complainant / informant</div><div className="fir-signature-line">Officer in charge · name / rank / number</div></div>
        </Section>
        <Section number={15} en="Date & time of dispatch to the court" ta="நீதிமன்றத்திற்கு அனுப்பப்பட்ட நாள் மற்றும் நேரம்">
          <Filled className="fir-dispatch-blank" />
        </Section>
      </div>
      <PageFooter recordId={record.record_id} page="Form · 2" />
    </div>

    <div className="fir-page fir-page-annexure">
      <div className="fir-draft-watermark" aria-hidden="true">DRAFT</div>
      <div className="fir-continuation">ANNEXURE A <span>ACCOUNT FOR OFFICER REVIEW</span></div>
      <h3>Source account and working English text</h3>
      <div className="fir-annexure-notice">The following text is machine-produced or officer-edited working material. It is not a signed, verified statement and is not the registered FIR contents.</div>
      <div className="fir-annexure-block"><h4>Original-language account / transcript</h4><p lang="ta">{draft.decision.narrative || 'Not provided.'}</p></div>
      <div className="fir-annexure-block"><h4>English translation / working text</h4><p>{draft.narrative_en || 'Not provided.'}</p></div>
      <div className="fir-annexure-block"><h4>System-assembled narrative</h4><p>{record.narrative?.en || 'Not available.'}</p></div>
      <div className="fir-annexure-bottom"><span>Officer verification and corrections:</span><div className="fir-ruled-space" /></div>
      <PageFooter recordId={record.record_id} page="Annexure A" />
    </div>
  </div>
}
