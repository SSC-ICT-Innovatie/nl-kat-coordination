================
What is OpenKAT?
================

OpenKAT is an open-source platform for continuously monitoring information systems and identifying security risks.

It helps you answer a simple question:

**“What do I know about my systems, and what should I be concerned about?”**

OpenKAT collects information about your systems from different sources, combines that information, and continuously analyzes it for vulnerabilities, configuration issues and other security risks. The results are presented as findings and reports that you can use to understand and manage your security posture.

How does OpenKAT work?
======================

OpenKAT works as a continuous cycle:

- **Discover** — Start with systems or assets you want to monitor, such as a hostname, IP address or URL.
- **Collect** — OpenKAT uses plugins to gather information from these assets and from external sources.
- **Build context** — The collected information is converted into objects and connected through OpenKAT's data model.
- **Analyze** — OpenKAT applies rules to the available information to identify vulnerabilities, configuration problems and other findings.
- **Expand and update** — Newly discovered information can trigger additional scans, while existing information can be refreshed over time.
- **Report** — Findings and collected information can be viewed in OpenKAT or turned into reports.

This means that OpenKAT does not treat every scan as an isolated event. Information discovered during one scan can provide the context for another scan.

For example, OpenKAT might start with a hostname. A DNS scan can discover an IP address, which can lead to a port scan. Open ports can reveal software or services, which can then be analyzed for vulnerabilities. Each step adds information to the picture of the system.

What makes OpenKAT different?
=============================

OpenKAT combines information from multiple security tools and sources in a common data model. This allows information to be connected, analyzed and followed over time rather than simply presenting the output of individual scanners.

Its modular architecture also means that scanning, normalization, analysis and reporting can be extended independently.

At the heart of OpenKAT are four concepts:

- **Objects** — representations of things discovered in your environment, such as IP addresses, hostnames and services.
- **Plugins** — (security) tools, scans and scripts that collect information.
- **Analysis** — rules that use the collected information to identify findings.
- **Reports** — accessible representations of the information and findings.

The developer documentation goes into more detail about these concepts and the modules that implement them.

How much does OpenKAT scan?
===========================

OpenKAT gives you control over how far it is allowed to go when scanning. Scan levels and indemnifications determine which actions OpenKAT is permitted to perform.

This is important because discovering information can range from passive, low-impact activities to scans that may have a greater impact on a system.

You therefore decide what OpenKAT is allowed to do within your environment.

Who is OpenKAT for?
===================

OpenKAT is particularly useful for organizations that need to monitor many systems or want to combine information from multiple security tools.

It can be used by organizations monitoring their own infrastructure, as well as organizations responsible for monitoring systems belonging to others, such as security teams, service providers and CSIRTs.

Why is OpenKAT open source?
===========================

OpenKAT was developed by the Dutch Ministry of Health and subsequently released as open-source software.

An open-source approach makes it possible for organizations to inspect, use and adapt the software. It also allows the OpenKAT community to contribute new functionality, integrations and improvements.

The modular architecture is intended to make these contributions reusable across different OpenKAT installations and use cases.

In short
========

OpenKAT continuously builds a picture of your information systems:

collect information → connect it → analyze it → discover more → report findings → repeat

The result is a continuously updated view of your systems and the security risks associated with them.
