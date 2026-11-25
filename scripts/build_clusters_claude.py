"""Builder output for cluster-based scoring (docs/CLUSTER_SCORING_PROTOCOL.md, Sec. 4-5).

    .venv/Scripts/python.exe scripts/build_clusters_claude.py

Clusters built 2026-11-19 by Claude (claude-opus-5-5) with the regulation-annotator
skill, from the cluster keys (annotation/cluster_keys.jsonl) and rule text printed
with scripts/reg_lookup.py in that session. The builder saw only the keys and the
rule text: no drafts, rankings, run outputs or results.

Every member carries a verbatim duty quote (checked against the corpus by this
script: it refuses to write if a quote is not found word for word) and a link to
the gold section. Link types used:
  cross_reference  the rule text of one section names the other
  same_trigger     both sections impose a duty triggered by the same consumer
                   event typical of the issue (a dispute, an error notice, an
                   identity-theft report, a validation request, a payment)
CFPB examination modules [protocol refs 1-3] informed the grouping, but no member
cites a module, because the builder did not check each pairing against a module
text; that link type is therefore not claimed.

Writes annotation/clusters_claude.jsonl (silver labels; reviewed next by a second
model, scripts/review_clusters.py).
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cfpb.pipeline.corpus import load_corpus  # noqa: E402

BUILDER = "llm:claude-opus-5-5 (regulation-annotator skill)"

# Verbatim duty quotes, as printed by reg_lookup.py on 2026-11-19.
Q = {
    # FCRA statute
    "1681i": ("1681i", "if the completeness or accuracy of any item of information contained in a consumer's file at a consumer reporting agency is disputed by the consumer and the consumer notifies the agency directly, or indirectly through a reseller, of such dispute, the agency shall, free of charge"),
    "1681s-2/b": ("1681s-2", "After receiving notice pursuant to section 1681i(a)(2) of this title of a dispute with regard to the completeness or accuracy of any information provided by a person to a consumer reporting agency, the person shall—"),
    "1681s-2/a6": ("1681s-2", "A person that furnishes information to any consumer reporting agency shall have in place reasonable procedures to respond to any notification that it receives from a consumer reporting agency under section 1681c–2 of this title relating to information resulting from identity theft, to prevent that person from refurnishing such blocked information."),
    "1681c-2": ("1681c-2", "a consumer reporting agency shall block the reporting of any information in the file of a consumer that the consumer identifies as information that resulted from an alleged identity theft, not later than 4 business days after the date of receipt by such agency of—"),
    "1681c-1": ("1681c-1", "who submits an identity theft report to a consumer reporting agency described in section 1681a(p) of this title that maintains a file on the consumer, if the agency has received appropriate proof of the identity of the requester, the agency shall—"),
    "1681e/b": ("1681e", "Whenever a consumer reporting agency prepares a consumer report it shall follow reasonable procedures to assure maximum possible accuracy of the information concerning the individual about whom the report relates."),
    "1681e/a": ("1681e", "Every consumer reporting agency shall maintain reasonable procedures designed to avoid violations of section 1681c of this title and to limit the furnishing of consumer reports to the purposes listed under section 1681b of this title."),
    "1681b/a": ("1681b", "any consumer reporting agency may furnish a consumer report under the following circumstances and no other:"),
    "1681b/f": ("1681b", "A person shall not use or obtain a consumer report for any purpose unless—"),
    "1681g": ("1681g", "Every consumer reporting agency shall, upon request, and subject to section 1681h(a)(1) of this title, clearly and accurately disclose to the consumer:"),
    "1681j": ("1681j", "shall make all disclosures pursuant to section 1681g of this title once during any 12-month period upon request of the consumer and without charge to the consumer."),
    "1681c": ("1681c", "no consumer reporting agency may make any consumer report containing any of the following items of information:"),
    # Regulation V
    "1022.43": ("1022.43", "a furnisher must conduct a reasonable investigation of a direct dispute if it relates to:"),
    "1022.42": ("1022.42", "Each furnisher must establish and implement reasonable written policies and procedures regarding the accuracy and integrity of the information relating to consumers that it furnishes to a consumer reporting agency."),
    "1022.123": ("1022.123", "Consumer reporting agencies shall develop and implement reasonable requirements for what information consumers shall provide to constitute proof of identity for purposes of sections 605A, 605B, and 609(a)(1) of the FCRA."),
    "1022.136": ("1022.136", "All nationwide consumer reporting agencies shall jointly design, fund, implement, maintain, and operate a centralized source for the purpose described in Paragraph (a) of this section."),
    # Regulation E
    "1005.11": ("1005.11", "A financial institution shall investigate promptly and, except as otherwise provided in this paragraph (c), shall determine whether an error occurred within 10 business days of receiving a notice of error."),
    "1005.6": ("1005.6", "A consumer's liability for an unauthorized electronic fund transfer or a series of related unauthorized transfers shall be determined as follows:"),
    "1005.18": ("1005.18", "For purposes of § 1005.6(b)(3), the 60-day period for reporting any unauthorized transfer shall begin on the earlier of:"),
    "1005.9": ("1005.9", "a financial institution shall send a periodic statement for each monthly cycle in which an electronic fund transfer has occurred"),
    "1005.10": ("1005.10", "A consumer may stop payment of a preauthorized electronic fund transfer from the consumer's account by notifying the financial institution orally or in writing at least three business days before the scheduled date of the transfer."),
    "1005.7": ("1005.7", "A financial institution shall provide the following disclosures, as applicable:"),
    # Regulation F
    "1006.14": ("1006.14", "A debt collector must not engage in any conduct the natural consequence of which is to harass, oppress, or abuse any person in connection with the collection of a debt"),
    "1006.18/a": ("1006.18", "A debt collector must not use any false, deceptive, or misleading representation or means in connection with the collection of any debt"),
    "1006.18/c2": ("1006.18", "Communicate or threaten to communicate to any person credit information that the debt collector knows or should know is false, including the failure to communicate that a disputed debt is disputed"),
    "1006.38": ("1006.38", "Upon receipt of a dispute submitted by the consumer in writing within the validation period, a debt collector must cease collection of the debt, or any disputed portion of the debt, until the debt collector:"),
    "1006.34": ("1006.34", "a debt collector must provide a consumer with the validation information required by paragraph (c) of this section either:"),
    "1006.30": ("1006.30", "a debt collector must not furnish to a consumer reporting agency, as defined in section 603(f) of the Fair Credit Reporting Act (15 U.S.C. 1681a(f)), information about a debt before the debt collector:"),
    "1006.6": ("1006.6", "if a consumer notifies a debt collector in writing that the consumer refuses to pay a debt or that the consumer wants the debt collector to cease further communication with the consumer, the debt collector must not communicate or attempt to communicate further with"),
    "1006.22": ("1006.22", "A debt collector must not use unfair or unconscionable means to collect or attempt to collect any debt"),
    "1006.26": ("1006.26", "A debt collector must not bring or threaten to bring a legal action against a consumer to collect a time-barred debt."),
    "1006.42": ("1006.42", "A debt collector who sends disclosures required by the Act and this part in writing or electronically must do so in a manner that is reasonably expected to provide actual notice, and in a form that the consumer may keep and access later."),
    # Regulation Z
    "1026.13": ("1026.13", "The creditor shall mail or deliver written acknowledgment to the consumer within 30 days of receiving a billing error notice"),
    "1026.12/a": ("1026.12", "no credit card shall be issued to any person except:"),
    "1026.12/b": ("1026.12", "The liability of a cardholder for unauthorized use of a credit card shall not exceed the lesser of $50 or the amount of money, property, labor, or services obtained by the unauthorized use before notification to the card issuer"),
    "1026.10": ("1026.10", "A creditor shall credit a payment to the consumer's account as of the date of receipt"),
    "1026.36": ("1026.36", "No servicer shall fail to credit a periodic payment to the consumer's loan account as of the date of receipt"),
    "1026.41": ("1026.41", "A servicer of a transaction subject to this section shall provide the consumer, for each billing cycle, a periodic statement meeting the requirements of paragraphs (b), (c), and (d) of this section."),
    "1026.5": ("1026.5", "The creditor shall mail or deliver a periodic statement as required by § 1026.7 for each billing cycle"),
    "1026.7": ("1026.7", "The creditor shall furnish the consumer with a periodic statement that discloses the following items, to the extent applicable:"),
    "1026.9": ("1026.9", "a creditor must provide a written notice of the change at least 45 days prior to the effective date of the change to each consumer who may be affected."),
    "1026.52": ("1026.52", "A card issuer must not impose a fee for violating the terms or other requirements of a credit card account under an open-end (not home-secured) consumer credit plan unless the dollar amount of the fee is consistent with paragraphs (b)(1) and (b)(2) of this section."),
    "1026.53": ("1026.53", "the card issuer must allocate the excess amount first to the balance with the highest annual percentage rate"),
    "1026.54": ("1026.54", "a card issuer must not impose finance charges as a result of the loss of a grace period"),
    "1026.55": ("1026.55", "a card issuer must not increase an annual percentage rate or a fee or charge required to be disclosed"),
    "1026.16": ("1026.16", "If a deferred interest offer is advertised, the deferred interest period must be stated in a clear and conspicuous manner in the advertisement."),
    "1026.60": ("1026.60", "The card issuer shall disclose the items in this paragraph on or with an application or a solicitation"),
    "1026.17": ("1026.17", "The creditor shall make the disclosures required by this subpart clearly and conspicuously in writing"),
    "1026.37": ("1026.37", "For each transaction subject to § 1026.19(e), the creditor shall disclose the information in this section:"),
    "1026.38": ("1026.38", "For each transaction subject to § 1026.19(f), the creditor shall disclose the information in this section:"),
}

X, S = "cross_reference", "same_trigger"

# key -> list of (quote id, tier, link type, link evidence). The gold section is always added as core.
CLUSTERS = {
    "1026.53|advertising-and-marketing-including-promotional-offers": [
        ("1026.16", "related", S, "promotional-offer terms (deferred interest) bear on how a card's balances and payments are treated"),
        ("1026.60", "related", S, "the promotional terms must be disclosed on the card application or solicitation"),
        ("1026.54", "related", S, "promotional balances and grace-period finance charges on the same card account")],
    "1026.19|applying-for-a-mortgage-or-refinancing-an-existing-mortgage": [
        ("1026.37", "related", X, "1026.37 sets the content of the Loan Estimate required by 1026.19(e)"),
        ("1026.38", "related", X, "1026.38 sets the Closing Disclosure required by 1026.19(f), against which tolerances are measured")],
    "1006.14|attempts-to-collect-debt-not-owed": [
        ("1006.38", "related", S, "consumer disputes the debt; collector must cease collection until it verifies"),
        ("1006.18/a", "related", S, "collecting a debt not owed can misrepresent the debt"),
        ("1006.6", "related", S, "the consumer's refusal to pay or cease request limits further communication"),
        ("1006.34", "related", S, "validation information for a debt the consumer does not recognise")],
    "1006.18|attempts-to-collect-debt-not-owed": [
        ("1006.38", "related", S, "consumer disputes the debt; collector must cease collection until it verifies"),
        ("1006.34", "related", S, "validation information for a debt the consumer does not recognise"),
        ("1006.22", "related", S, "collecting an amount not owed or not authorised"),
        ("1006.30", "related", S, "collector's credit reporting of the disputed debt"),
        ("1681s-2/b", "related", S, "collector as furnisher must investigate a dispute relayed by a CRA"),
        ("1022.43", "related", S, "collector as furnisher must investigate a direct dispute about liability or identity theft")],
    "1006.38|attempts-to-collect-debt-not-owed": [
        ("1006.34", "related", X, "1006.38(d)(2) applies to disputes within the validation period set by the 1006.34 notice"),
        ("1006.18/a", "related", S, "collecting a debt not owed can misrepresent the debt"),
        ("1006.22", "related", S, "collecting an amount not owed or not authorised"),
        ("1022.43", "related", S, "collector as furnisher: direct dispute of liability"),
        ("1681s-2/b", "related", S, "collector as furnisher: dispute relayed by a CRA")],
    "1681i|attempts-to-collect-debt-not-owed": [
        ("1681s-2/b", "core", X, "1681s-2(b) duties are triggered by the CRA's notice under 1681i(a)(2): same dispute, furnisher side"),
        ("1681e/b", "related", S, "accuracy of the disputed collection tradeline"),
        ("1681c-2", "related", S, "block if the debt resulted from identity theft"),
        ("1681g", "related", S, "consumer's right to see the file entries being disputed")],
    "1681s-2|attempts-to-collect-debt-not-owed": [
        ("1022.43", "core", S, "same furnisher duty to investigate, for a dispute sent directly to it"),
        ("1681i", "core", X, "1681s-2(b) is triggered by the CRA's notice under 1681i(a)(2): CRA side of the same dispute"),
        ("1022.42", "related", S, "furnisher accuracy policies for the disputed data"),
        ("1006.18/c2", "related", S, "a collector-furnisher must not report credit information it knows is false or omit that it is disputed"),
        ("1006.38", "related", S, "collector-furnisher must cease collection pending verification of a written dispute"),
        ("1681c-2", "related", X, "1681s-2(a)(6) refers to identity-theft blocks under 1681c-2")],
    "1026.18|charged-fees-or-interest-you-didn-t-expect": [
        ("1026.17", "core", X, "1026.17 sets form and timing for the closed-end disclosures whose content 1026.18 lists")],
    "1006.14|communication-tactics": [
        ("1006.6", "related", S, "limits on when and how a collector may communicate with the consumer")],
    "1006.18|communication-tactics": [
        ("1006.14", "related", S, "repeated calls in collecting the same debt"),
        ("1006.6", "related", S, "limits on collector communications"),
        ("1006.38", "related", S, "disputed debt must not be collected until verified"),
        ("1006.30", "related", S, "collector's credit reporting of the debt"),
        ("1681s-2/b", "related", S, "collector as furnisher of the reported information")],
    "1006.6|communication-tactics": [
        ("1006.14", "related", S, "continued contact after a cease request can be harassment; 1006.14(h) covers a requested medium")],
    "1681c-2|credit-monitoring-or-identity-theft-protection-services": [
        ("1681c-1", "related", S, "fraud and extended alerts for the same identity-theft victim"),
        ("1022.123", "related", X, "1022.123 sets proof of identity for FCRA sections 605A and 605B (1681c-1, 1681c-2)"),
        ("1681s-2/a6", "related", X, "1681s-2(a)(6) requires furnishers to respond to 1681c-2 block notices"),
        ("1681i", "related", S, "dispute of the identity-theft items in the file")],
    "1006.6|electronic-communications": [
        ("1006.14", "related", S, "1006.14(h) bars a medium the consumer asked the collector not to use")],
    "1006.18|false-statements-or-representation": [
        ("1006.38", "related", S, "consumer disputes the amount; collector must cease collection until it verifies"),
        ("1006.22", "related", S, "collecting an amount not authorised by the agreement or law"),
        ("1006.34", "related", S, "validation information states the amount of the debt"),
        ("1681s-2/b", "related", S, "collector as furnisher of the misstated amount")],
    "1006.38|false-statements-or-representation": [
        ("1006.18/a", "related", S, "misstating the amount of the debt"),
        ("1006.22", "related", S, "collecting an amount not authorised"),
        ("1006.34", "related", X, "1006.38(d)(2) applies to disputes within the validation period set by the 1006.34 notice")],
    "1022.43|false-statements-or-representation": [
        ("1681s-2/b", "core", S, "same furnisher duty to investigate, for a dispute relayed by a CRA"),
        ("1022.42", "related", S, "furnisher accuracy policies for the disputed amount"),
        ("1681i", "related", S, "CRA side of the same dispute")],
    "1026.10|fees-or-interest": [
        ("1026.55", "related", S, "limits on increasing the card's APR"),
        ("1026.9", "related", S, "advance notice of a change in terms such as a rate increase"),
        ("1026.13", "related", S, "a disputed finance charge can be asserted as a billing error")],
    "1026.13|fees-or-interest": [
        ("1026.52", "related", S, "limits on the disputed penalty fees"),
        ("1026.55", "related", S, "limits on increasing the disputed rate"),
        ("1026.54", "related", S, "limits on the disputed finance charges"),
        ("1026.7", "related", X, "1026.13(b) billing error notices are sent to the address disclosed under 1026.7"),
        ("1026.10", "related", S, "payment crediting that drives the disputed interest"),
        ("1026.53", "related", S, "payment allocation that drives the disputed interest")],
    "1026.16|fees-or-interest": [
        ("1026.53", "related", S, "allocation of payments to deferred-interest balances"),
        ("1026.54", "related", S, "limits on imposing finance charges"),
        ("1026.13", "related", S, "disputed interest can be asserted as a billing error")],
    "1026.5|fees-or-interest": [
        ("1026.52", "related", S, "limits on the late fee charged"),
        ("1026.7", "related", X, "1026.5(b)(2) requires the periodic statement described in 1026.7"),
        ("1026.10", "related", S, "crediting of the payment the fee is tied to"),
        ("1026.13", "related", S, "disputed fee can be asserted as a billing error")],
    "1026.52|fees-or-interest": [
        ("1026.5", "related", S, "statement timing that conditions late treatment"),
        ("1026.13", "related", S, "disputed fee can be asserted as a billing error"),
        ("1026.7", "related", S, "fees disclosed on the periodic statement")],
    "1005.11|fraud-or-scam": [
        ("1005.6", "related", S, "liability limits for the unauthorized transfer under dispute")],
    "1022.43|getting-a-credit-card": [
        ("1681s-2/b", "core", S, "same furnisher duty to investigate, for a dispute relayed by a CRA"),
        ("1026.12/a", "related", S, "card issued without the consumer's request or application"),
        ("1681c-2", "related", S, "block of the fraudulent account at the CRAs"),
        ("1022.42", "related", S, "furnisher accuracy policies for the disputed account")],
    "1026.12|getting-a-credit-card": [
        ("1022.43", "related", S, "issuer as furnisher must investigate a direct dispute of liability or identity theft"),
        ("1681s-2/b", "related", S, "issuer as furnisher: dispute relayed by a CRA"),
        ("1026.13", "related", S, "charges on the unrequested account can be asserted as billing errors")],
    "1681b|getting-a-credit-card": [
        ("1026.12/a", "related", S, "card issued without the consumer's request or application"),
        ("1022.43", "related", S, "direct dispute of the account and inquiry with the issuer"),
        ("1681s-2/b", "related", S, "issuer as furnisher: dispute relayed by a CRA")],
    "1006.18|getting-a-loan": [
        ("1006.38", "related", S, "consumer disputes the debt; collector must cease collection until it verifies"),
        ("1006.34", "related", S, "validation information for a debt the consumer does not recognise"),
        ("1006.30", "related", S, "collector's credit reporting of the debt"),
        ("1681s-2/b", "related", S, "collector as furnisher: dispute relayed by a CRA"),
        ("1022.43", "related", S, "collector as furnisher: direct dispute about identity theft")],
    "1681b|improper-use-of-your-report": [
        ("1681i", "core", S, "dispute of the unrecognised inquiries with the CRA"),
        ("1681e/a", "related", X, "1681e(a) requires procedures to limit furnishing to the purposes in 1681b"),
        ("1681c-2", "related", S, "block if the inquiries resulted from identity theft"),
        ("1681c-1", "related", S, "fraud alert for a consumer seeing unknown inquiries"),
        ("1681g", "related", S, "disclosure of who received the consumer's report")],
    "1681c-2|improper-use-of-your-report": [
        ("1681i", "core", S, "dispute of the identity-theft items with the CRA"),
        ("1681c-1", "related", S, "fraud and extended alerts for the same victim"),
        ("1022.123", "related", X, "1022.123 sets proof of identity for FCRA section 605B (1681c-2)"),
        ("1681s-2/a6", "related", X, "1681s-2(a)(6) requires furnishers to respond to 1681c-2 block notices"),
        ("1681b/a", "related", S, "permissible purpose for the report use complained of")],
    "1681i|improper-use-of-your-report": [
        ("1681s-2/b", "core", X, "1681s-2(b) is triggered by the CRA's notice under 1681i(a)(2)"),
        ("1681b/a", "related", S, "permissible purpose for the report use complained of"),
        ("1681e/a", "related", S, "procedures to limit furnishing to permissible purposes"),
        ("1681c-2", "related", S, "block if the items resulted from identity theft"),
        ("1681g", "related", S, "disclosure of the file and its recipients")],
    "1006.18|incorrect-information-on-your-report": [
        ("1681s-2/b", "core", S, "collector as furnisher: investigation of the reporting dispute relayed by a CRA"),
        ("1022.43", "core", S, "collector as furnisher: investigation of a direct dispute"),
        ("1006.38", "related", S, "disputed debt must not be collected until verified"),
        ("1006.30", "related", S, "collector's credit reporting of the debt"),
        ("1022.42", "related", S, "furnisher accuracy policies")],
    "1681c-2|incorrect-information-on-your-report": [
        ("1681i", "core", S, "dispute of the same incorrect items with the CRA"),
        ("1681s-2/a6", "related", X, "1681s-2(a)(6) requires furnishers to respond to 1681c-2 block notices"),
        ("1022.123", "related", X, "1022.123 sets proof of identity for FCRA section 605B (1681c-2)"),
        ("1681c-1", "related", S, "fraud and extended alerts for the same victim"),
        ("1681e/b", "related", S, "accuracy procedures for the file")],
    "1681i|incorrect-information-on-your-report": [
        ("1681s-2/b", "core", X, "1681s-2(b) is triggered by the CRA's notice under 1681i(a)(2)"),
        ("1681e/b", "related", S, "accuracy procedures for the disputed information"),
        ("1681c-2", "related", S, "block if the items resulted from identity theft"),
        ("1681g", "related", S, "disclosure of the file being disputed"),
        ("1681c", "related", S, "obsolete items that may not be reported")],
    "1005.11|managing-an-account": [
        ("1005.6", "related", S, "liability limits for the unauthorized transfer under dispute"),
        ("1005.9", "related", X, "1005.11(b) dates the notice of error from the periodic statement required by 1005.9")],
    "1005.6|managing-an-account": [
        ("1005.11", "core", S, "error resolution for the same unauthorized transfer"),
        ("1005.7", "related", X, "1005.6(a) conditions liability on the disclosures required by 1005.7(b)")],
    "1022.43|managing-the-loan-or-lease": [
        ("1681s-2/b", "core", S, "same furnisher duty to investigate, for a dispute relayed by a CRA"),
        ("1022.42", "related", S, "furnisher accuracy policies")],
    "1022.43|problem-when-making-payments": [
        ("1681s-2/b", "core", S, "same furnisher duty to investigate, for a dispute relayed by a CRA"),
        ("1022.42", "related", S, "furnisher accuracy policies")],
    "1026.10|problem-when-making-payments": [
        ("1026.13", "related", S, "failure to credit a payment can be asserted as a billing error (1026.13(a)(4))"),
        ("1026.53", "related", S, "allocation of the same payment")],
    "1681c-2|problem-with-a-company-s-investigation-into-an-existing-problem": [
        ("1681i", "core", S, "the CRA's reinvestigation of the same items"),
        ("1681s-2/a6", "related", X, "1681s-2(a)(6) requires furnishers to respond to 1681c-2 block notices"),
        ("1022.123", "related", X, "1022.123 sets proof of identity for FCRA section 605B (1681c-2)"),
        ("1681c-1", "related", S, "fraud and extended alerts for the same victim")],
    "1005.11|problem-with-a-lender-or-other-company-charging-your-account": [
        ("1005.6", "related", S, "liability limits for the unauthorized transfer under dispute"),
        ("1005.10", "related", S, "preauthorized debits taken on the wrong day or for the wrong amount")],
    "1005.11|problem-with-a-purchase-or-transfer": [
        ("1005.18", "core", X, "1005.18(e) modifies 1005.11 error resolution for prepaid accounts"),
        ("1005.6", "related", S, "liability limits for the unauthorized transfer under dispute")],
    "1005.18|problem-with-a-purchase-or-transfer": [
        ("1005.11", "core", X, "1005.18(e) modifies 1005.11 error resolution for prepaid accounts"),
        ("1005.6", "core", X, "1005.18(e)(1) modifies the 60-day period of 1005.6(b)(3)")],
    "1022.43|problem-with-a-purchase-shown-on-your-statement": [
        ("1026.13", "core", S, "the purchase dispute on a card statement is a billing error the issuer must resolve"),
        ("1681s-2/b", "related", S, "issuer as furnisher: dispute relayed by a CRA"),
        ("1026.12/b", "related", S, "liability limit if the charge was unauthorized")],
    "1026.12|problem-with-a-purchase-shown-on-your-statement": [
        ("1026.13", "core", S, "the same charge disputed as a billing error"),
        ("1022.43", "related", S, "issuer as furnisher: direct dispute of the reported balance")],
    "1026.13|problem-with-a-purchase-shown-on-your-statement": [
        ("1026.12/b", "core", S, "liability limit for the unauthorized charge under dispute")],
    "1006.18|took-or-threatened-to-take-negative-or-legal-action": [
        ("1006.26", "core", S, "threat to sue on a time-barred debt")],
    "1006.14|trouble-during-payment-process": [
        ("1026.36", "related", S, "servicer's duty to credit mortgage payments"),
        ("1026.41", "related", S, "servicer's periodic statements for the mortgage")],
    "1026.13|trouble-during-payment-process": [
        ("1026.36", "core", S, "servicer's duty to credit the mortgage payment on receipt"),
        ("1026.10", "related", S, "creditor's duty to credit a payment on receipt"),
        ("1026.41", "related", S, "servicer's periodic statements for the mortgage")],
    "1005.6|trouble-using-the-card": [
        ("1005.11", "core", S, "error resolution for the same ATM transfer"),
        ("1005.18", "related", X, "1005.18(e)(1) modifies 1005.6 for prepaid accounts")],
    "1026.12|trouble-using-your-card": [
        ("1026.13", "related", S, "disputed charges on the same card")],
    "1681e|unable-to-get-your-credit-report-or-credit-score": [
        ("1681g", "core", S, "duty to disclose the file to the consumer on request"),
        ("1681j", "related", X, "1681j makes the 1681g disclosures free once a year"),
        ("1022.136", "related", S, "centralized source for requesting the annual disclosure"),
        ("1022.123", "related", X, "1022.123 sets proof of identity for FCRA section 609(a)(1) (1681g) requests"),
        ("1681i", "related", S, "dispute of the inaccurate file the consumer cannot obtain")],
    "1005.11|unexpected-or-other-fees": [
        ("1005.18", "core", X, "1005.18(e) modifies 1005.11 error resolution for prepaid accounts"),
        ("1005.9", "related", S, "periodic statement showing the disputed fees")],
    "1006.30|written-notification-about-debt": [
        ("1006.34", "related", S, "validation notice the consumer says was not received"),
        ("1006.42", "related", S, "manner of sending the required notice"),
        ("1006.38", "related", S, "consumer disputes the debt; collector must cease collection until it verifies"),
        ("1006.18/c2", "related", S, "reporting the debt without noting a dispute")],
    "1006.34|written-notification-about-debt": [
        ("1006.42", "core", X, "1006.34(a)(1)(i) requires the validation notice to be sent in the manner required by 1006.42"),
        ("1006.38", "related", S, "disputes and verification during the validation period"),
        ("1006.30", "related", S, "no furnishing before the collector contacts the consumer"),
        ("1006.18/a", "related", S, "misleading statements about the debt")],
    "1006.38|written-notification-about-debt": [
        ("1006.34", "related", X, "1006.38(d)(2) applies to disputes within the validation period set by the 1006.34 notice"),
        ("1006.42", "related", S, "manner of sending the verification"),
        ("1006.18/a", "related", S, "misleading statements about the debt"),
        ("1006.30", "related", S, "collector's credit reporting of the debt")],
    "1681i|written-notification-about-debt": [
        ("1681s-2/b", "core", X, "1681s-2(b) is triggered by the CRA's notice under 1681i(a)(2)"),
        ("1681e/b", "related", S, "accuracy of the disputed collection tradeline"),
        ("1681g", "related", S, "disclosure of the file entries being disputed")],
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip()


def main() -> None:
    keys = [json.loads(l) for l in open(ROOT / "annotation" / "cluster_keys.jsonl", encoding="utf-8")]
    missing = {k["key"] for k in keys} ^ set(CLUSTERS)
    if missing:
        sys.exit(f"cluster keys and builder entries differ: {sorted(missing)}")
    corpus = load_corpus([str(ROOT / "chunking" / "data" / "processed" / "chunks.jsonl")])
    sec_text = {}
    for qid, (sec, quote) in Q.items():
        if sec not in sec_text:
            sec_text[sec] = norm(" ".join(c.text for c in corpus.chunks if c.section == sec))
        if norm(quote) not in sec_text[sec]:
            sys.exit(f"quote {qid} not found verbatim in {sec}")
    rows = []
    for k in keys:
        members = [{"section": k["gold_section"], "tier": "core", "link_type": "gold", "link_evidence": "gold section",
                    "duty_quote": None}]
        for qid, tier, link, ev in CLUSTERS[k["key"]]:
            sec, quote = Q[qid]
            assert sec != k["gold_section"] and sec not in {m["section"] for m in members}, (k["key"], sec)
            members.append({"section": sec, "tier": tier, "link_type": link, "link_evidence": ev, "duty_quote": quote})
        assert len(members) - 1 <= 6, k["key"]
        rows.append({"key": k["key"], "issue": k["issue"], "gold_section": k["gold_section"],
                     "gold_regulation": k["gold_regulation"], "members": members, "builder": BUILDER,
                     "date": str(date.today()),
                     "edition_notes": "rule text: eCFR as of 2026-10-13 and U.S. Code 2024 ed. (corpus); exam modules informed grouping only"})
    out = ROOT / "annotation" / "clusters_claude.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    n = sum(len(r["members"]) - 1 for r in rows)
    print(f"wrote {out}: {len(rows)} clusters, {n} proposed members besides gold; all {len(Q)} quotes verified verbatim")


if __name__ == "__main__":
    main()
