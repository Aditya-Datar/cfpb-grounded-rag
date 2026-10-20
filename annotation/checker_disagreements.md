# Checker set disagreements (claude-opus-5-5 vs chatgpt)

Agreement 76.0%, Cohen's kappa 0.540, 12 to adjudicate.

## K03

**Sentence:** The furnisher must complete its investigation and report the results to the consumer before the expiration of the period under section 611(a)(1) of the FCRA.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1022-1022.43-e]
§ 1022.43 Direct disputes.
(e) Duty of furnisher after receiving a direct dispute notice. After receiving a dispute notice from a consumer pursuant to paragraphs (c) and (d) of this section, the furnisher must:
(1) Conduct a reasonable investigation with respect to the disputed information;
(2) Review all relevant information provided by the consumer with the dispute notice;
(3) Complete its investigation of the dispute and report the results of the investigation to the consumer before the expiration of the period under section 611(a)(1) of the FCRA (15 U.S.C. 1681i(a)(1)) within which a consumer reporting agency would be required to complete its action if the consumer had elected to dispute the information under that section; and
(4) If the investigation finds that the information reported was inaccurate, promptly notify each consumer reporting agency to which the furnisher provided inaccurate information of that determination and provide to the consumer reporting agency any correction to that information that is necessary to make the information provided by the furnisher accurate.
```

## K04

**Sentence:** The debt collector must cease any conduct that could be deemed harassing, oppressive, or abusive and must refrain from placing telephone calls that violate these provisions.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1006-1006.14-a]
§ 1006.14 Harassing, oppressive, or abusive conduct.
(a) In general. A debt collector must not engage in any conduct the natural consequence of which is to harass, oppress, or abuse any person in connection with the collection of a debt, including, but not limited to, the conduct described in paragraphs (b) through (h) of this section.

[12-1006-1006.14-b-1]
§ 1006.14 Harassing, oppressive, or abusive conduct.
(b) Repeated or continuous telephone calls or telephone conversations—
(1) In general. In connection with the collection of a debt, a debt collector must not place telephone calls or engage any person in telephone conversation repeatedly or continuously with intent to annoy, abuse, or harass any person at the called number.

[12-1006-1006.14-b-2]
§ 1006.14 Harassing, oppressive, or abusive conduct.
(b) Repeated or continuous telephone calls or telephone conversations—
(2) Telephone call frequencies; presumptions of compliance and violation.
(i) Subject to the exclusions in paragraph (b)(3) of this section, a debt collector is presumed to comply with paragraph (b)(1) of this section and FDCPA section 806(5) (15 U.S.C. 1692d(5)) if the debt collector places a telephone call to a particular person in connection with the collection of a particular debt neither:
(A) More than seven times within seven consecutive days; nor
(B) Within a period of seven consecutive days after having had a telephone conversation with the person in connection with the collection of such debt. The date of the telephone conversation is the first day of the seven-consecutive-day period.
(ii) Subject to the exclusions in paragraph (b)(3) of this section, a debt collector is presumed to violate paragraph (b)(1) of this section and FDCPA section 806(5) if the debt collector places a telephone call to a particular person in connection with the collection of a particular debt in excess of either of the telephone call frequencies described in paragraph (b)(2)(i) of this section.
```

## K06

**Sentence:** The financial institution must comply with all applicable requirements of the Act and this part with respect to prepaid accounts
For unauthorized transfers the institution must apply the modified limitations on liability and error resolution requirements including the rule that the 60‑day reporting period begins on the earlier of the date the consumer electronically accesses the account with the unauthorized transfer reflected or the date the institution sends a written history reflecting the transfer
The institution may limit the consumer's liability for an unauthorized transfer as provided under §1005.6(b)(3) for any transfer reported within 120 days after the transfer was credited or debited
The institution must provide the required pre‑acquisition disclosures before the consumer acquires the prepaid account

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1005-1005.18-a]
§ 1005.18 Requirements for financial institutions offering prepaid accounts.
(a) Coverage. A financial institution shall comply with all applicable requirements of the Act and this part with respect to prepaid accounts except as modified by this section. For rules governing government benefit accounts, see § 1005.15.

[12-1005-1005.18-e-1]
§ 1005.18 Requirements for financial institutions offering prepaid accounts.
(e) Modified limitations on liability and error resolution requirements—
(1) Modified limitations on liability requirements. A financial institution that provides information under paragraph (c)(1) of this section shall comply with the following:
(i) For purposes of § 1005.6(b)(3), the 60-day period for reporting any unauthorized transfer shall begin on the earlier of:
(A) The date the consumer electronically accesses the consumer's account under paragraph (c)(1)(ii) of this section, provided that the electronic account transaction history made available to the consumer reflects the unauthorized transfer; or
(B) The date the financial institution sends a written history of the consumer's account transactions requested by the consumer under paragraph (c)(1)(iii) of this section in which the unauthorized transfer is first reflected.
(ii) A financial institution may comply with paragraph (e)(1)(i) of this section by limiting the consumer's liability for an unauthorized transfer as provided under § 1005.6(b)(3) for any transfer reported by the consumer within 120 days after the transfer was credited or debited to the consumer's account.

[12-1005-1005.18-b-1-i]
§ 1005.18 Requirements for financial institutions offering prepaid accounts.
(b) Pre-acquisition disclosure requirements—
(1) Timing of disclosures—
(i) General. Except as provided in paragraph (b)(1)(ii) or (iii) of this section, a financial institution shall provide the disclosures required by paragraph (b) of this section before a consumer acquires a prepaid account. When a prepaid account is used for disbursing funds to a consumer, and the financial institution or third party making the disbursement does not offer any alternative means for the consumer to receive those funds in lieu of accepting the prepaid account, for purposes of this paragraph, the disclosures required by paragraph (b) of this section may be provided at the time the consumer receives the prepaid account.
```

## K19

**Sentence:** Additionally, the consumer must report an unauthorized transfer that appears on a periodic statement within 60 days of the statement’s transmittal to avoid liability for subsequent transfers; otherwise liability may extend to transfers after the 60‑day period that the institution shows would not have occurred with timely notice.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1005-1005.6-b-3]
§ 1005.6 Liability of consumer for unauthorized transfers.
(b) Limitations on amount of liability. A consumer's liability for an unauthorized electronic fund transfer or a series of related unauthorized transfers shall be determined as follows:
(3) Periodic statement; timely notice not given. A consumer must report an unauthorized electronic fund transfer that appears on a periodic statement within 60 days of the financial institution's transmittal of the statement to avoid liability for subsequent transfers. If the consumer fails to do so, the consumer's liability shall not exceed the amount of the unauthorized transfers that occur after the close of the 60 days and before notice to the institution, and that the institution establishes would not have occurred had the consumer notified the institution within the 60-day period. When an access device is involved in the unauthorized transfer, the consumer may be liable for other amounts set forth in paragraphs (b)(1) or (b)(2) of this section, as applicable.
```

## K20

**Sentence:** If the company reasonably determines that the block was in error, based on a material misrepresentation, or that the consumer obtained goods/services/money from the blocked transaction, it may decline to block or rescind the block.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[15-fcra-1681c-2-c]
§1681c–2. Block of information resulting from identity theft
(c) Authority to decline or rescind
(1) In general
A consumer reporting agency may decline to block, or may rescind any block, of information relating to a consumer under this section, if the consumer reporting agency reasonably determines that—
(A) the information was blocked in error or a block was requested by the consumer in error;
(B) the information was blocked, or a block was requested by the consumer, on the basis of a material misrepresentation of fact by the consumer relevant to the request to block; or
(C) the consumer obtained possession of goods, services, or money as a result of the blocked transaction or transactions.
(2) Notification to consumer
If a block of information is declined or rescinded under this subsection, the affected consumer shall be notified promptly, in the same manner as consumers are notified of the reinsertion of information under section 1681i(a)(5)(B) of this title.
(3) Significance of block
For purposes of this subsection, if a consumer reporting agency rescinds a block, the presence of information in the file of a consumer prior to the blocking of such information is not evidence of whether the consumer knew or should have known that the consumer obtained possession of any goods, services, or money as a result of the block.
```

## K21

**Sentence:** The furnisher must conduct a reasonable investigation of a direct dispute that relates to whether there is or has been identity theft or fraud against the consumer.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1022-1022.43-a]
§ 1022.43 Direct disputes.
(a) General rule. Except as otherwise provided in this section, a furnisher must conduct a reasonable investigation of a direct dispute if it relates to:
(1) The consumer's liability for a credit account or other debt with the furnisher, such as direct disputes relating to whether there is or has been identity theft or fraud against the consumer, whether there is individual or joint liability on an account, or whether the consumer is an authorized user of a credit account;
(2) The terms of a credit account or other debt with the furnisher, such as direct disputes relating to the type of account, principal balance, scheduled payment amount on an account, or the amount of the credit limit on an open-end account;
(3) The consumer's performance or other conduct concerning an account or other relationship with the furnisher, such as direct disputes relating to the current payment status, high balance, date a payment was made, the amount of a payment made, or the date an account was opened or closed; or
(4) Any other information contained in a consumer report regarding an account or other relationship with the furnisher that bears on the consumer's creditworthiness, credit standing, credit capacity, character, general reputation, personal characteristics, or mode of living.
```

## K25

**Sentence:** Telephone calls placed with the consumer's prior consent given directly to the debt collector and within seven days of receiving that consent do not count toward the telephone call frequencies.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1006-1006.14-b-3]
§ 1006.14 Harassing, oppressive, or abusive conduct.
(b) Repeated or continuous telephone calls or telephone conversations—
(3) Certain telephone calls excluded from the telephone call frequencies. Telephone calls placed to a person do not count toward the telephone call frequencies described in paragraph (b)(2)(i) of this section if they are:
(i) Placed with such person's prior consent given directly to the debt collector and within a period no longer than seven consecutive days after receiving the prior consent, with the date the debt collector receives prior consent counting as the first day of the seven-consecutive-day period;
(ii) Not connected to the dialed number; or
(iii) Placed to the persons described in § 1006.6(d)(1)(ii) through (vi).
```

## K32

**Sentence:** The collector must also provide the validation information set forth in § 1006.34(c)(2), including its name and address, the consumer's name and address, the creditor name at itemization, account number, current creditor name, itemization date, debt amount at itemization, itemization of current amount, and current debt amount.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1006-1006.34-c-2]
§ 1006.34 Notice for validation of debts.
(c) Validation information. Pursuant to paragraph (a)(1) of this section, a debt collector must provide the following validation information.
(2) Information about the debt. Except as provided in paragraph (c)(5) of this section:
(i) The debt collector's name and the mailing address at which the debt collector accepts disputes and requests for original-creditor information.
(ii) The consumer's name and mailing address.
(iii) If the debt collector is collecting a debt related to a consumer financial product or service as defined in § 1006.2(f), the name of the creditor to whom the debt was owed on the itemization date.
(iv) The account number, if any, associated with the debt on the itemization date, or a truncated version of that number.
(v) The name of the creditor to whom the debt currently is owed.
(vi) The itemization date.
(vii) The amount of the debt on the itemization date.
(viii) An itemization of the current amount of the debt reflecting interest, fees, payments, and credits since the itemization date. A debt collector may disclose the itemization on a separate page provided in the same communication with a validation notice, if the debt collector includes on the validation notice, where the itemization would have appeared, a statement referring to that separate page.
(ix) The current amount of the debt.
```

## K37

**Sentence:** The furnisher must conduct an investigation and review all relevant information provided by the consumer
The furnisher must complete its investigation and report the results to the consumer before the expiration of the period under section 611(a)(1) of the FCRA
If the investigation finds the information inaccurate, incomplete, or unverifiable, the furnisher must modify, delete, or permanently block the reporting of that information and notify each consumer reporting agency to which it furnished the inaccurate information
The consumer reporting agency must then promptly delete or modify the inaccurate or unverifiable item from the consumer's file and notify the furnisher of the action

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[15-fcra-1681s-2-b-piece-1]
§1681s–2. Responsibilities of furnishers of information to consumer reporting agencies
(b) Duties of furnishers of information upon notice of dispute
(1) In general
After receiving notice pursuant to section 1681i(a)(2) of this title of a dispute with regard to the completeness or accuracy of any information provided by a person to a consumer reporting agency, the person shall—
(A) conduct an investigation with respect to the disputed information;
(B) review all relevant information provided by the consumer reporting agency pursuant to section 1681i(a)(2) of this title;
(C) report the results of the investigation to the consumer reporting agency;
(D) if the investigation finds that the information is incomplete or inaccurate, report those results to all other consumer reporting agencies to which the person furnished the information and that compile and maintain files on consumers on a nationwide basis; and
(E) if an item of information disputed by a consumer is found to be inaccurate or incomplete or cannot be verified after any reinvestigation under paragraph (1), for purposes of reporting to a consumer reporting agency only, as appropriate, based on the results of the reinvestigation promptly—
(i) modify that item of information;
(ii) delete that item of information; or
(iii) permanently block the reporting of that item of information.
(2) Deadline

[12-1022-1022.43-e]
§ 1022.43 Direct disputes.
(e) Duty of furnisher after receiving a direct dispute notice. After receiving a dispute notice from a consumer pursuant to paragraphs (c) and (d) of this section, the furnisher must:
(1) Conduct a reasonable investigation with respect to the disputed information;
(2) Review all relevant information provided by the consumer with the dispute notice;
(3) Complete its investigation of the dispute and report the results of the investigation to the consumer before the expiration of the period under section 611(a)(1) of the FCRA (15 U.S.C. 1681i(a)(1)) within which a consumer reporting agency would be required to complete its action if the consumer had elected to dispute the information under that section; and
(4) If the investigation finds that the information reported was inaccurate, promptly notify each consumer reporting agency to which the furnisher provided inaccurate information of that determination and provide to the consumer reporting agency any correction to that information that is necessary to make the information provided by the furnisher accurate.

[15-fcra-1681i-a-5-piece-1]
§1681i. Procedure in case of disputed accuracy
(5) Treatment of inaccurate or unverifiable information
(A) In general
If, after any reinvestigation under paragraph (1) of any information disputed by a consumer, an item of the information is found to be inaccurate or incomplete or cannot be verified, the consumer reporting agency shall—
(i) promptly delete that item of information from the file of the consumer, or modify that item of information, as appropriate, based on the results of the reinvestigation; and
(ii) promptly notify the furnisher of that information that the information has been modified or deleted from the file of the consumer.
(B) Requirements relating to reinsertion of previously deleted material
(i) Certification of accuracy of information
If any information is deleted from a consumer's file pursuant to subparagraph (A), the information may not be reinserted in the file by the consumer reporting agency unless the person who furnishes the information certifies that the information is complete and accurate.
(ii) Notice to consumer
```

## K42

**Sentence:** Under 15 U.S.C. 1681c-2(d), a consumer reporting agency must block the consumer report from any subsequent use when the consumer identifies information in the file that resulted from identity theft and the agency is a reseller of that information.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[15-fcra-1681c-2-d-piece-1]
§1681c–2. Block of information resulting from identity theft
(d) Exception for resellers
(1) No reseller file
This section shall not apply to a consumer reporting agency, if the consumer reporting agency—
(A) is a reseller;
(B) is not, at the time of the request of the consumer under subsection (a), otherwise furnishing or reselling a consumer report concerning the information identified by the consumer; and
(C) informs the consumer, by any means, that the consumer may report the identity theft to the Bureau to obtain consumer information regarding identity theft.
(2) Reseller with file
The sole obligation of the consumer reporting agency under this section, with regard to any request of a consumer under this section, shall be to block the consumer report maintained by the consumer reporting agency from any subsequent use, if—
(A) the consumer, in accordance with the provisions of subsection (a), identifies, to a consumer reporting agency, information in the file of the consumer that resulted from identity theft; and
(B) the consumer reporting agency is a reseller of the identified information.
(3) Notice
```

## K43

**Sentence:** During the first year after account opening, the total amount of fees a consumer is required to pay with respect to a credit card account must not exceed 25 percent of the credit limit in effect when the account is opened, except for late payment fees, over-the-limit fees, and returned-payment fees.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1026-1026.52-a]
§ 1026.52 Limitations on fees.
(a) Limitations during first year after account opening—
(1) General rule. Except as provided in paragraph (a)(2) of this section, the total amount of fees a consumer is required to pay with respect to a credit card account under an open-end (not home-secured) consumer credit plan during the first year after account opening must not exceed 25 percent of the credit limit in effect when the account is opened. For purposes of this paragraph, an account is considered open no earlier than the date on which the account may first be used by the consumer to engage in transactions.
(2) Fees not subject to limitations. Paragraph (a) of this section does not apply to:
(i) Late payment fees, over-the-limit fees, and returned-payment fees; or
(ii) Fees that the consumer is not required to pay with respect to the account.
(3) Rule of construction. Paragraph (a) of this section does not authorize the imposition or payment of fees or charges otherwise prohibited by law.
```

## K44

**Sentence:** The creditor must disclose the balance on which the finance charge was computed and explain how that balance was determined, using the term Balance Subject to Interest Rate.

- claude-opus-5-5: supported
- chatgpt: unsupported
- **Adjudicated label:** 

```text
[12-1026-1026.7-b-5]
§ 1026.7 Periodic statement.
The creditor shall furnish the consumer with a periodic statement that discloses the following items, to the extent applicable:
(b) Rules affecting open-end (not home-secured) plans. The requirements of paragraph (b) of this section apply only to plans other than home-equity plans subject to the requirements of § 1026.40.
(5) Balance on which finance charge computed. The amount of the balance to which a periodic rate was applied and an explanation of how that balance was determined, using the term Balance Subject to Interest Rate. When a balance is determined without first deducting all credits and payments made during the billing cycle, the fact and the amount of the credits and payments shall be disclosed. As an alternative to providing an explanation of how the balance was determined, a creditor that uses a balance computation method identified in § 1026.60(g) may, at the creditor's option, identify the name of the balance computation method and provide a toll-free telephone number where consumers may obtain from the creditor more information about the balance computation method and how resulting interest charges were determined. If the method used is not identified in § 1026.60(g), the creditor shall provide a brief explanation of the method used.
```
