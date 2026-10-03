*(Client draft received 2026-09-23 via Bhavin's email. Client's paper — AtliQ has not yet marked up.)*

# SERVICES AGREEMENT
## (Dienstleistungs- und Werkvertrag — English version)

**Contract No. RWA-2026-014**

between

**Rheinwerk Analytics GmbH**, Leopoldstraße 184, 80804 München, Germany, registered in the commercial register of the Local Court (Amtsgericht) of Munich under HRB 241873, VAT ID DE318442907, represented by its Managing Director (Geschäftsführer), Mr. Stefan Brandt
— hereinafter "**Client**" —

and

**AtliQ Technologies Pvt Ltd**, 4th Floor, Baner Business Bay, Pune 411045, Maharashtra, India, CIN U72900MH2019PTC321456, represented by its Director
— hereinafter "**Supplier**" —

— Client and Supplier each a "**Party**", together the "**Parties**" —

## Preamble

Client provides industrial analytics and predictive maintenance software to mid-sized manufacturing companies in the DACH region. Client intends to replace the batch-based data ingestion layer of its "Rheinwerk Insight" platform with a scalable, near-real-time data pipeline architecture. Supplier has experience in the design and implementation of cloud data pipelines. The Parties therefore agree as follows.

## § 1 Definitions

1.1 "**Platform**" means Client's Rheinwerk Insight software-as-a-service platform.
1.2 "**Work Results**" means all results created by Supplier for Client under this Agreement, including source code, configurations, pipeline definitions, documentation and test cases.
1.3 "**Milestone**" means a defined stage of the project as set out in Annex 1.
1.4 "**Milestone Fee**" means the remuneration allocated to a Milestone in Annex 2.
1.5 "**Client Data**" means all data made available by Client or its customers, including sensor, machine and maintenance data and any personal data contained therein.
1.6 "**GDPR**" means Regulation (EU) 2016/679 (General Data Protection Regulation).

## § 2 Subject Matter and Scope of Services

2.1 Supplier shall design, implement and hand over a new data ingestion and processing layer for the Platform, comprising in particular:
   (a) streaming ingestion of machine sensor data (OPC UA / MQTT) from Client's customers' plants into Client's EU cloud environment;
   (b) a medallion-architecture data lakehouse (raw, cleansed, curated layers) with data quality checks;
   (c) migration of 22 existing batch jobs to the new pipeline framework;
   (d) orchestration, monitoring and alerting; and
   (e) documentation and a two-week knowledge transfer to Client's platform engineering team.
2.2 The detailed specification is set out in Annex 1 (Leistungsbeschreibung / Statement of Work).
2.3 Supplier shall perform the services with its own personnel, primarily remotely from India. Supplier personnel shall attend on-site workshops in Munich at the start of the project and for the knowledge transfer.
2.4 Changes to the scope of services require a written change request agreed by both Parties (§ 12.3).

## § 3 Client's Cooperation Duties

3.1 Client shall provide Supplier with timely access to the required cloud environments, source systems, test data and contact persons.
3.2 Client shall nominate a project lead with decision-making authority.
3.3 Delays caused by Client's failure to fulfil its cooperation duties shall extend the relevant deadlines accordingly.

## § 4 Remuneration and Payment

4.1 The total fixed remuneration for the services under this Agreement is **EUR 88,000** (eighty-eight thousand euros) net, payable in accordance with the Milestones in Annex 2.
4.2 Supplier shall invoice each Milestone Fee after acceptance of the relevant Milestone. Invoices are payable within thirty (30) days of receipt without deduction.
4.3 All amounts are net. Where the reverse-charge procedure under § 13b UStG applies, the invoice shall so indicate. Withholding taxes, if any, shall be handled in accordance with the applicable double taxation agreement between Germany and India, and Client shall provide the relevant certificates.
4.4 Travel expenses for on-site workshops shall be reimbursed at cost up to a maximum of EUR 6,000 in total, subject to prior approval.

## § 5 Acceptance (Abnahme)

5.1 Each Milestone requiring acceptance shall be submitted to Client for acceptance testing. Client shall declare acceptance within ten (10) working days of submission if the Work Results conform in all material respects to Annex 1.
5.2 Minor defects shall not entitle Client to refuse acceptance; they shall be recorded in the acceptance protocol and remedied within a reasonable period.
5.3 If Client fails to declare acceptance or to specify material defects within the period set out in § 5.1, acceptance shall be deemed to have been granted.

## § 6 Supplier Tools and Rights of Use

6.1 Supplier shall deliver the services using its proprietary data-pipeline accelerator "**PipeKit**", comprising reusable ingestion connectors, transformation templates, data quality rule libraries and orchestration modules. PipeKit shall be incorporated into the Work Results to reduce implementation time and cost.
6.2 Supplier hereby grants Client a perpetual, irrevocable, non-exclusive, worldwide, royalty-free right to use, reproduce, modify and operate PipeKit as incorporated in the Work Results, for the purposes of operating, maintaining and further developing the Platform, including for the benefit of Client's customers. Client may sub-license this right to its affiliated companies and to service providers acting on its behalf.
6.3 Supplier warrants that it is the sole owner of all intellectual property rights in PipeKit, that it is entitled to grant the rights set out in § 6.2, and that PipeKit and its use under this Agreement do not infringe any rights of third parties.
6.4 Supplier shall indemnify Client against all third-party claims arising from any breach of the warranty in § 6.3, in accordance with § 10.
6.5 Except for PipeKit, Client shall acquire the exclusive, perpetual, transferable and unrestricted right of use in all Work Results created specifically for Client, upon full payment of the relevant Milestone Fee.
6.6 Open-source components may be used only with Client's prior approval and subject to their respective licence terms, which Supplier shall list in the documentation.

## § 7 Warranty for Defects

7.1 Supplier warrants that the Work Results conform to the specification in Annex 1 at the time of acceptance.
7.2 The warranty period is twelve (12) months from acceptance.
7.3 Supplier shall remedy defects by rectification or new delivery at its option. If remedy fails twice, Client may reduce the remuneration for the affected Milestone or withdraw from the affected part of the Agreement.

## § 8 Delay

8.1 Deadlines for the Milestones are set out in Annex 2.
8.2 If Supplier is in default with a Milestone for reasons for which it is responsible, Client may claim a contractual penalty (Vertragsstrafe) of 0.5% of the Milestone Fee of the affected Milestone for each full week of delay, up to a maximum of 5% of that Milestone Fee.
8.3 No penalty shall be payable to the extent the delay is caused by Client, including by failure to fulfil its cooperation duties under § 3, or by force majeure.
8.4 The contractual penalty shall be credited against any claim for damages for the same delay.

## § 9 Liability

9.1 The Parties shall be liable without limitation for damage caused intentionally or by gross negligence, for injury to life, body or health, and under the Product Liability Act (Produkthaftungsgesetz).
9.2 In the case of slightly negligent breach of a material contractual obligation (Kardinalpflicht), liability shall be limited to the foreseeable damage typical for this type of contract, and in any event to the total remuneration under this Agreement.
9.3 Otherwise, liability for slight negligence is excluded.
9.4 Liability for loss of data is limited to the cost of restoration that would have been incurred had Client carried out regular data backups in line with good practice.

## § 10 Indemnification

10.1 Each Party shall indemnify the other against third-party claims resulting from its culpable breach of this Agreement.
10.2 The indemnified Party shall notify the indemnifying Party without delay of any claim, shall not acknowledge any claim without consent, and shall leave the conduct of the defence to the indemnifying Party.

## § 11 Confidentiality

11.1 The Parties shall keep confidential all business and trade secrets of the other Party that come to their knowledge in connection with this Agreement, and shall use them only for the performance of this Agreement.
11.2 This obligation does not apply to information that is publicly known, was already known to the receiving Party, or is required to be disclosed by law or official order.
11.3 The confidentiality obligation shall continue for five (5) years after termination of this Agreement.

## § 12 Term, Termination, Changes

12.1 This Agreement enters into force upon signature by both Parties and ends upon acceptance of the final Milestone and expiry of the warranty period.
12.2 The right of either Party to terminate for good cause (aus wichtigem Grund) remains unaffected. Good cause exists in particular if the other Party materially breaches its obligations and fails to remedy the breach within thirty (30) days of written notice. Upon termination by Client for convenience (§ 648 BGB), Supplier shall be entitled to the agreed remuneration for services rendered plus compensation for committed costs.
12.3 Change requests shall be submitted in writing. Supplier shall assess the impact on effort, schedule and remuneration within five (5) working days. Changes become binding only when agreed in writing.

## § 13 Data Protection

13.1 To the extent Supplier processes personal data on behalf of Client, the Parties shall conclude the Data Processing Agreement pursuant to Art. 28 GDPR attached as **Annex 3**, which forms an integral part of this Agreement.
13.2 Transfers of personal data to India shall be based on the EU Standard Contractual Clauses (Module 2, Controller-to-Processor) incorporated in Annex 3, supplemented by the technical and organisational measures described therein.
13.3 Supplier shall ensure that its personnel are bound to confidentiality and data secrecy and receive appropriate data protection training.

## § 14 Governing Law and Place of Jurisdiction

14.1 This Agreement shall be governed by the laws of the Federal Republic of Germany, excluding the UN Convention on Contracts for the International Sale of Goods (CISG).
14.2 The exclusive place of jurisdiction for all disputes arising out of or in connection with this Agreement shall be Munich, Germany.

## § 15 Final Provisions

15.1 Amendments and supplements to this Agreement, including this written form clause, must be made in writing. Text form (e-mail) is sufficient for change requests under § 12.3.
15.2 Should any provision of this Agreement be or become invalid, the validity of the remaining provisions shall not be affected. The Parties shall replace the invalid provision with a valid provision that comes closest to the economic purpose of the invalid provision.
15.3 Supplier may subcontract parts of the services only with Client's prior written consent.
15.4 In the event of discrepancies between this English version and any German translation, the English version shall prevail.
15.5 The following Annexes form part of this Agreement: Annex 1 (Statement of Work), Annex 2 (Milestones and Remuneration), Annex 3 (Data Processing Agreement incl. SCCs).

## Annex 2 — Milestones and Remuneration

| Milestone | Description | Deadline | Milestone Fee (EUR) |
|---|---|---|---|
| M1 | Architecture design, PipeKit set-up in Client EU environment | Start + 4 weeks | 13,200 |
| M2 | Streaming ingestion (OPC UA / MQTT) and raw layer | Start + 10 weeks | 22,000 |
| M3 | Cleansed and curated layers; data quality framework | Start + 16 weeks | 22,000 |
| M4 | Migration of 22 batch jobs; orchestration and monitoring | Start + 22 weeks | 22,000 |
| M5 | Documentation and knowledge transfer | Start + 24 weeks | 8,800 |
| | **Total** | | **88,000** |

## Signatures

Munich, ______________ 2026

**Rheinwerk Analytics GmbH**
______________________
Stefan Brandt, Managing Director (Geschäftsführer)

Pune, ______________ 2026

**AtliQ Technologies Pvt Ltd**
______________________
Name: ______________________
Title: ______________________
