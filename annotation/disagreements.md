# Annotator disagreements (26 of 198)

A = `llm_labels_claude-opus-5-5.jsonl`, B = `llm_labels_chatgpt.jsonl`. A human adjudicator records the final label.

## 23887307
- **A:** NONE (conf 1): The narrative is two lines and describes an account the consumer did not open, so it is not clearly the consumer's account under Reg E. Best guess NONE (identity theft); low confidence.
- **B:** E 1005.6 (conf 1): Unauthorized-transfer liability is a tentative fit because the account ownership, transfer method, and any dispute handling are unspecified.
- **B's review:** prefers claude -> NONE: 1005.6 requires an unauthorized electronic transfer involving the consumer's account; this narrative establishes neither the transfer mechanism nor an account loss borne by the consumer. NONE is better supported than inferring those missing facts.
- **Final (human):** 

## 20053768
- **A:** FCRA 1681s-2(a)(2) (conf 1): The inaccurate $6,000 balance comes from the original creditor as furnisher; its duty to correct and update is 1681s-2(a)(2). The respondent is the debt buyer, so confidence is low.
- **B:** F 1006.18(c)(2) (conf 2): False balance reporting is the best collector provision, but the redacted text obscures which entity reports the balance.
- **B's review:** prefers claude -> FCRA 1681s-2: The alleged false balance is attributed to the former creditor that sold the debt, so the furnisher correction duty in 1681s-2(a)(2) fits better than collector misconduct under 1006.18. The mismatch between that reporter and the named debt buyer still limits certainty.
- **Final (human):** 

## 15574957
- **A:** FCRA 1681s-2(a)(6) (conf 1): A creditor reporting a collection on an identity-theft account implicates furnisher identity-theft duties in 1681s-2(a)(6); sparse facts mean low confidence.
- **B:** V 1022.43(a)(1) (conf 1): Direct furnisher investigation is the tentative fit because the named respondent is a bank and the alleged collector cannot be identified.
- **B's review:** prefers chatgpt -> V 1022.43: The stated grievance disputes liability for an unfamiliar credit account, the topic covered by 1022.43(a)(1). The narrative does not describe a CRA identity-theft block notification or an identity-theft report submitted to this furnisher to trigger 1681s-2(a)(6).
- **Final (human):** 

## 17303744
- **A:** FCRA 1681i(a)(1) (conf 3): Dispute of unrecognized negative items lodged with Experian: CRA reinvestigation duty.
- **B:** FCRA 1681c-2(a) (conf 2): The FTC report and denial of ownership support the identity-theft blocking convention, although the attachment contents are unavailable.
- **B's review:** prefers chatgpt -> FCRA 1681c-2: Unlike a bare accuracy dispute, this complaint identifies unfamiliar accounts and expressly supplies an FTC report and affidavit, supporting the rubric's identity-theft-report route to 1681c-2(a). The unseen report's adequacy remains uncertain, so the label does not establish that every blocking prerequisite was met.
- **Final (human):** 

## 15999483
- **A:** F 1006.18(c)(2) (conf 2): The grievance is a collector reporting a disputed, allegedly fraudulent debt, which matches 1006.18(c)(2) as in item 20536937. The duty to verify disputed debts (1006.38) is the runner-up.
- **B:** V 1022.43(a)(1) (conf 2): The main grievance is disputed liability and reporting, which remains within the credit-reporting corpus.
- **B's review:** prefers claude -> F 1006.18: The narrative describes a successor collecting and reporting disputed student-loan debt rather than the originating lender. On that collector reading, the rubric specifically assigns allegedly false collector credit reporting to 1006.18(c)(2), with collector coverage still requiring confirmation.
- **Final (human):** 

## 22217070
- **A:** NONE (conf 1): Kikoff is collecting its own subscription charge, so Reg F's validation notice duty (the CFPB issue category) does not apply. The sparse facts give no clear in-scope duty.
- **B:** V 1022.43(a)(1) (conf 1): A direct dispute about account liability is the tentative fit; the narrative is too thin to establish fraud or a qualifying dispute notice.
- **B's review:** prefers claude -> NONE: The consumer acknowledges a Kikoff account and primarily objects to an unexpected annual subscription charge. The facts do not clearly identify inaccurate furnished information or a qualifying direct dispute under 1022.43; subscription and negative-option obligations are outside the corpus.
- **Final (human):** 

## 17208754
- **A:** FCRA 1681s-2(b) (conf 1): Against Capital One, the in-scope claim is the disputed 90-day late passed through TransUnion, triggering the furnisher investigation duty in 1681s-2(b). The goodwill requests themselves create no duty.
- **B:** NONE (conf 2): For the named respondent, the stated request is goodwill removal; disputes against other bureaus and collectors do not establish Capital One's reinvestigation duty.
- **B's review:** prefers chatgpt -> NONE: The company-specific allegation against Capital One is failure to answer a goodwill request, which creates no deletion duty under the rubric. A separate TransUnion dispute is mentioned, but receipt of CRA-relayed notice by Capital One, required by 1681s-2(b), is not established.
- **Final (human):** 

## 18411360
- **A:** F 1006.14(a) (conf 1): The consumer's emphasis is the repeated, aggressive contact, pointing to 1006.14. The not-owed debt and implied threats make 1006.18 a close runner-up, and the vague facts mean low confidence.
- **B:** F 1006.18(c)(2) (conf 2): The allegedly false collection tradeline is the most concrete complaint; knowledge of falsity and the threat details remain unclear.
- **B's review:** prefers claude -> F 1006.14: The narrative emphasizes repeated aggressive communications, implied threats, and their distressing effects, fitting the general harassment duty in 1006.14(a). False credit reporting under 1006.18(c)(2) is a plausible secondary issue, but is less central to the described conduct.
- **Final (human):** 

## 19181545
- **A:** F 1006.18(c)(2) (conf 2): A collector continuing to report a disputed debt fits 1006.18(c)(2), consistent with items 20536937 and 15999483. The CRA-relayed investigation duty itself is the FCRA statute's (1681s-2(b)).
- **B:** FCRA 1681s-2(b) (conf 3): The narrative explicitly describes CRA disputes and a furnisher verification response, making the relayed-dispute investigation duty the closest fit.
- **B's review:** prefers chatgpt -> FCRA 1681s-2: The consumer expressly disputed through all three CRAs and challenges the collector's resulting verification investigation. That route matches 1681s-2(b), which requires the furnisher to investigate after CRA notice, more specifically than the general false-reporting prohibition in 1006.18(c)(2).
- **Final (human):** 

## 18659009
- **A:** F 1006.38(d)(2) (conf 2): Against the collector, the main grievance is the unanswered verification request, which is the 1006.38(d)(2) duty. The CRA reinvestigation part of the complaint falls under the FCRA statute.
- **B:** F 1006.18(c)(2) (conf 2): The named respondent is the debt collector, so the CRA-only method-of-verification duty does not govern its conduct.
- **B's review:** prefers claude -> F 1006.38: For the named debt buyer, the central unfulfilled request is verification of the debt and ownership while collection reporting continues. The rubric assigns that grievance to 1006.38(d)(2), although writing and receipt within the validation period remain unconfirmed.
- **Final (human):** 

## 21513066
- **A:** F 1006.18(c)(2) (conf 1): Labelled by the facts, not the cited statute: a collector reporting a debt the consumer disputes, which matches 1006.18(c)(2). The GLBA privacy theory (Reg P) is outside the corpus and likely inapplicable to credit reporting.
- **B:** NONE (conf 2): The stated grievance concerns privacy authorization; it does not identify an actual debt inaccuracy or a prior unanswered validation request.
- **B's review:** prefers chatgpt -> NONE: The concrete demand concerns authorization to possess and share financial information, without identifying a false debt fact or alleging omission of a dispute notation. Those facts do not establish the false-or-unmarked-disputed reporting element of 1006.18(c)(2); the asserted privacy duty lies outside the corpus.
- **Final (human):** 

## 19422448
- **A:** FCRA 1681s-2(a)(6) (conf 1): A furnisher re-reporting fraudulent accounts that had been removed points to the duty to prevent refurnishing identity-theft information, 1681s-2(a)(6). Department of Education identity theft rules also apply.
- **B:** V 1022.43(a)(1) (conf 2): The respondent is the furnisher and liability is directly disputed; the narrative does not establish a submitted identity-theft report for the refurnishing prohibition.
- **B's review:** prefers claude -> FCRA 1681s-2: The main grievance is renewed furnishing of accounts previously removed as fraudulent, which the rubric specifically routes to 1681s-2(a)(6). Whether the furnisher received the required identity-theft report or CRA block notification remains unknown, rather than established.
- **Final (human):** 

## 15914096
- **A:** FCRA 1681i(a)(1) (conf 2): Consumer asks a CRA to block accounts pending verification and remove them if inaccurate; no identity theft report is described, so reinvestigation (1681i) with block (1681c-2) as runner-up.
- **B:** FCRA 1681c-2(a) (conf 2): The express block request for unauthorized accounts fits identity-theft blocking, but the required report and proof are not described.
- **B's review:** prefers claude -> FCRA 1681i: The consumer requests blocking pending verification and deletion if the accounts prove inaccurate, making reinvestigation under 1681i(a)(1) the better-supported duty. No identity-theft report or express allegation identifying the information as resulting from identity theft is described for the more specific 1681c-2 process.
- **Final (human):** 

## 15396023
- **A:** FCRA 1681c-2(a) (conf 2): Consumer reports remaining fraudulent items at TransUnion after partial removal; framed as fraud, so block duty 1681c-2(a), reinvestigation runner-up.
- **B:** FCRA 1681i(a)(1) (conf 2): The narrative supports an unresolved accuracy dispute without describing an identity-theft report or specific statutory block packet.
- **B's review:** prefers chatgpt -> FCRA 1681i: The facts describe an unresolved dispute after partial deletion, but do not describe an identity-theft block request or report. Reinvestigation under 1681i(a)(1) is better supported than inferring the specialized blocking prerequisites in 1681c-2(a).
- **Final (human):** 

## 17362489
- **A:** NONE (conf 2): The consumer gave account details to a scammer, and the loss stems from fraudulent funds passed through the account, not an unauthorized withdrawal. The bank's chargeback of those funds is contractual.
- **B:** E 1005.11(c) (conf 1): Unauthorized EFT claim handling is tentative because the transaction mechanism, actual authority, and dispute history are unclear.
- **B's review:** prefers claude -> NONE: The narrative identifies an account restriction and responsibility for funds passed through the account, without identifying an unauthorized EFT or an error notice satisfying 1005.11(b). NONE is the better abstention, but the text also does not establish Claude's more specific theory of returned fraudulent deposits.
- **Final (human):** 

## 21757875
- **A:** E 1005.6(b) (conf 2): The dispute is how much the consumer must bear for confirmed unauthorized transfers reported late, which is governed by the liability limits in 1005.6(b) (as modified for benefit accounts in 1005.15).
- **B:** E 1005.18(e)(1) (conf 2): The rubric directs late-reporting prepaid claims to the modified start of the reporting period, with government-benefit modifications as runner-up.
- **B's review:** prefers chatgpt -> E 1005.18: The shared rubric expressly assigns prepaid claims denied only for late reporting to 1005.18(e)(1), with 1005.15 as runner-up for government-benefit cards. That modified reporting-period starting point is more specific to this grievance than the general liability limits in 1005.6.
- **Final (human):** 

## 18107288
- **A:** NONE (conf 2): Misleading 'fee-free' advertising for a deposit account is a Reg DD/UDAAP matter. Reg E's ATM fee notice (1005.16) applies to ATM operators.
- **B:** E 1005.7(b)(5) (conf 2): EFT fee disclosure is the closest corpus duty, though the types of fees and initial disclosures are not provided.
- **B's review:** prefers claude -> NONE: The grievance challenges fee-free deposit-account advertising and an ATM locator, rather than the initial EFT-service disclosures required by 1005.7. Regulation DD and deceptive-advertising duties are the better fit outside the corpus; the record does not identify an omitted initial disclosure of a specific institution-imposed EFT fee.
- **Final (human):** 

## 23218918
- **A:** Z 1026.13(a)(3) (conf 2): An unaccepted charge on a credit card statement is a billing error under 1026.13(a)(3). The late fees and collection that followed depend on how the issuer handled the error.
- **B:** Z 1026.12(b) (conf 2): The issuer has not been described as investigating and denying a billing claim, so the unauthorized-use convention is the closer fit.
- **B's review:** prefers chatgpt -> Z 1026.12: The consumer alleges an unauthorized renewal charge, without describing an issuer investigation and denial or goods not delivered as agreed. The rubric routes unauthorized credit-card use without that denial history to 1026.12(b), making Claude's 1026.13(a)(3) less directly supported.
- **Final (human):** 

## 23084662
- **A:** NONE (conf 1): Reg Z requires crediting payments on receipt, but here the payment did not reach this issuer on time because the sender misrouted it, so 1026.10 is not violated on these facts.
- **B:** Z 1026.10(a) (conf 2): Payment crediting is the closest duty, but liability depends on when the intended creditor actually received the payment.
- **B's review:** prefers claude -> NONE: 1026.10(a) requires crediting a payment as of receipt, whereas the narrative says the transfer was sent to the wrong recipient and later returned. It does not establish that Bilt or its creditor received and then delayed crediting the payment; the requested interest reimbursement is not an established in-corpus duty on these facts.
- **Final (human):** 

## 20834286
- **A:** Z 1026.10(a) (conf 1): The consumer disputes payments being treated as late, which is closest to the payment-crediting duty. If they simply paid after the due date on bad advice, no rule is violated, so confidence is low.
- **B:** Z 1026.5(b)(2)(ii)(A) (conf 2): The missing-statement timing duty is the closest convention; inability to access email does not alone prove the issuer failed timely delivery.
- **B's review:** prefers neither -> NONE: The facts describe incorrect payment-date advice and inability to access statements, but not delayed crediting after receipt under 1026.10(a) or failure to mail or deliver statements under 1026.5(b)(2)(ii)(A). The better-supported grievance is contractual or deceptive servicing advice outside these cited duties.
- **Final (human):** 

## 21260751
- **A:** NONE (conf 1): Recurring charges the consumer set up and did not cancel are generally authorized, even after card reissuance. A billing-error claim (1026.13) is the runner-up if the consumer disputed in writing.
- **B:** Z 1026.13(a)(1) (conf 2): Billing-error handling is the closest fit, but card expiration alone does not revoke an existing recurring-payment authorization.
- **B's review:** prefers claude -> NONE: The stated premise is that expiration itself ended existing recurring-payment authority, without alleging cancellation before the disputed charges or another billing error. Under 1026.13(a)(1), lack of actual, implied, or apparent authority is required; expiration and unawareness alone do not establish it, so NONE is better supported.
- **Final (human):** 

## 18672068
- **A:** Z 1026.54(a) (conf 1): Interest charged to a pay-in-full customer points to the grace-period finance-charge limits in 1026.54(a). If it was a computational error, it would be a billing error (1026.13(a)(5)). The cause is not stated, so confidence is low.
- **B:** Z 1026.13(a)(6) (conf 2): The concrete request is clarification and documentation of the statement charge, with written-notice prerequisites uncertain.
- **B's review:** prefers chatgpt -> Z 1026.13: The concrete unresolved request is an explanation and documentary calculation of the interest charge, matching 1026.13(a)(6). The record does not establish the particular loss-of-grace-period calculation prohibited by 1026.54(a), while qualifying written-notice requirements for 1026.13 remain uncertain.
- **Final (human):** 

## 24401680
- **A:** Z 1026.55(a) (conf 1): Rising interest charges on a card are governed by the APR-increase limits in 1026.55 (notice in 1026.9). A variable-rate change permitted by 1026.55(b) would mean no violation, so confidence is low.
- **B:** Z 1026.13(a)(6) (conf 2): The facts request an explanation of interest amounts without establishing that the APR itself increased.
- **B's review:** prefers chatgpt -> Z 1026.13: The consumer requests clarification of rising dollar interest charges, fitting 1026.13(a)(6), with written-notice prerequisites still uncertain. An increase from approximately $90 to $100 does not itself establish an increased APR or specified fee or charge governed by 1026.55(a).
- **Final (human):** 

## 15771889
- **A:** Z 1026.12(a) (conf 1): A one-line claim that the issuer's account is fraudulent maps to card issuance without request (1026.12(a)). The credit-reporting angle makes furnisher duties (1681s-2) the runner-up.
- **B:** V 1022.43(a)(1) (conf 1): A direct account-liability dispute is the closest factual fit; the narrative does not describe actual card issuance or prior dispute details.
- **B's review:** prefers chatgpt -> V 1022.43: The only narrative fact is that a reported account is fraudulent and does not belong to the consumer, supporting a furnisher liability dispute under 1022.43(a)(1). Actual issuance of an unrequested card, required for 1026.12(a), is not described beyond the selected issue category.
- **Final (human):** 

## 17902984
- **A:** NONE (conf 1): No card was issued, and the respondent is not a CRA, so no in-scope duty of this issuer clearly governs. Inquiry removal would run through the CRAs' block duty (1681c-2).
- **B:** FCRA 1681b(f) (conf 2): The card was still pending, so the relevant duty concerns the lender's purpose for obtaining the report rather than completed unsolicited issuance.
- **B's review:** prefers chatgpt -> FCRA 1681b: 1681b(f) restricts any person's obtaining or using a consumer report to authorized purposes, so its coverage is not limited to CRAs. The fraudulent-application inquiry implicates that issuer duty even though no card was issued; the actual permissible-purpose facts remain uncertain.
- **Final (human):** 

## 22147352
- **A:** F 1006.30(a)(1) (conf 2): Reporting a debt before any communication with the consumer is the passive-collection ban in 1006.30(a)(1). The missing validation notice (1006.34) is the runner-up.
- **B:** F 1006.34(a) (conf 2): The main grievance is missing validation information; the text does not establish that no other prior contact occurred.
- **B's review:** prefers chatgpt -> F 1006.34: The consumer specifically alleges missing validation information and dispute rights, which are governed by 1006.34(a). The complaint does not state there was no prior conversation or properly sent message, so the pre-reporting-contact element of 1006.30(a)(1) cannot be inferred solely from missing validation information.
- **Final (human):** 
