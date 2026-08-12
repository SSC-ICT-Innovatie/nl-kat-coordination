---
authors: JP Bruins Slot <jpbruinsslot@gmail.com>
state: published
discussion: https://github.com/minvws/nl-kat-coordination/pull/3425
labels: process
---

# RFD 0002: Code of Conduct: Code Review

## Introduction

Code reviews are an essential part of the software development process,
ensuring that the codebase remains bug-free, clean, maintable and efficient. It
helps to spot potential issues, while fostering collaboration and knowledge
sharing among team members. For both authors and reviewers, approaching code
reviews with the right mindset and strategies can significantly improve the
quality of the code and the efficiency of the review process.

By adhering to these best practices, both authors and reviewers can contribute
to a more effective and enjoyable code review process, ultimately leading to
higher-quality software and stronger team dynamics.

Having a code of conduct for code reviews can help set expectations, establish
a positive and respectful environment, and ensure that the review process is
productive and beneficial for all team members.

## Authors

1. **Mind your reviewer**

   Make choices or options that minimize time and cognitive load for the
   reviewer, such as opting for multiple small independent PR's instead of a
   massive one that covers a relatively large surface of the code base. Be
   especially mindful of this with potential big refactorings.

2. **Satisfy preconditions**

   Ensure that your code is ready for review before you send it, and if you
   feel that it is not entirely there yet please mark it as 'draft' to signal
   this to potential reviewers. Things to check before putting your code up for
   review:

   - Validate your PR by doing a 'self-review' by checking your changes,
   - It should work and is able to run,
   - There should be no unresolved merge conflicts,
   - Have adequate testing that pass,
   - And respect the style and coding guidelines.

   This is respectful of reviewer time and can sometimes save you a review
   round trip. If you're looking for an early review then make this clear.

   Try to make a habit to review early and often, and to ask for feedback
   early. When you feel that you could use some input on your draft PR then ask
   for it. This can help you to avoid costly mistakes and rework later on.

3. **Provide context**

   When opening a PR for review be clear to your reviewer about your
   expectations. In terms of the review, this means specifying in the
   description of the PR, the kind of reviewing as well as who should review
   what, using which level of scrutiny and rigor.

   Add comments or give explanations with your code about the thought process,
   and show what choices you've made and why.

   Be cognizant that enough context is provided for the reviewer to understand
   the changes you've made.

   When necessary schedule a call or a meeting to discuss the changes in more
   detail, and walk the reviewer through the changes.

4. **Remember that communication can be hard**

   Difference in understanding or opinions are to be expected in the context of
   code review. Always assume competence and goodwill from the reviewer, and
   that the other person has your best interests (and those of your project) at
   heart. As with giving feedback, receiving feedback requires that the author
   is open to **constructive** criticism and feedback.

## Reviewers

1.  **Look for the following**

    As a reviewer look for the following in a pull request[^1]. In no
    particular order:

    1.1 _Design_

    Does this change integrate well with the rest of the system? Is it
    consistent with the existing design and architecture?

    1.2 _Functionality_

    Does the code behave as the author likely intended? Is the way the code
    behaves good for its users? This includes the users of the software as well
    as the developers who will be working with the code. Think about edge
    cases, look for concurrency problems, try to think like a user, and make
    sure that there are no bugs that you see just by reading the code.

    1.3 _Complexity_

    Is the change more complex than it needs to be? **Too complex** usually
    means: "can't be understood quickly by code readers". It can also mean
    "developers are likely to introduce bugs when they try or modify this
    code".

    Be cautious of over-engineering, where developers make the code more
    generalized than necessary or include features that aren't currently
    required. Encourage developers to address the problem that needs solving
    right now, rather than focusing on a potential issue that might arise in
    the future.

    1.4 _Tests_

    Does the code have correct and well-designed automated tests? Ask for unit,
    integration, or end-to-end tests as appropriate for the change.

    Will the tests actually fail when the code is broken? If the code changes,
    will they begin to produce false positives? Do the tests make clear and
    meaningful assertions? Are they appropriately divided across different test
    methods?

    Keep in mind that tests are also code that needs maintenance. Avoid
    allowing complexity in tests just because they aren't part of the main
    codebase.

    1.5 _Naming_

    Did the developer choose clear names for variables, classes, methods, etc.?
    Does the name accurately describe the purpose, behavior, and intent of the
    code it represents?

    1.6 _Style and Conventions_

    Does the code follow our style and coding guidelines? Are there any
    violations of the style guide?

    1.7 _Consistency_

    Preferably the author should maintain consistency with the existing code.
    This includes consistency in naming, style, structure, and design patterns.

    This makes sure that the codebase is easier to understand and maintain.
    When a substantial change should be made to the existing code that would
    cause inconsistencies, it should be discussed with the team, and be
    addressed in a separate issue.

    1.8 _Comments_

    Are the comments clear and useful? Do they explain why the code is written
    in a certain way? Do they explain the intent behind the code? Are they
    up-to-date?

    1.9 _Documentation_

    Did the developer also update relevant documentation? This includes README
    files, API documentation, and any other relevant documentation.

2.  **Assume competence and goodwill**

    Be positive, polite and respectful.

3.  **Be mindful of the power dynamic**[^2]

    As a reviewer be mindful of the inherent power dynamic between a reviewer
    and reviewee. This arises from the temporary authority the reviewer holds.
    When the reviewer holds gatekeeping authority the power dynamic is more
    permanent. This dynamic can be beneficial, fostering collaboration and
    improving code quality, but it can also lead to abuse of power if not
    handled responsibly.

    The reviewer has the power to delay or reject a PR, creating a potential
    for misuse that might obstruct progress, or to exert unnecessary dominance
    over the reviewee. Whether by nitpicking, imposing unnecessary demands, or
    prolonging the review process.

    This authority must by used judiciously and with respect for the
    submitter’s time and effort. Abuse of this power, whether through trivial
    criticisms or using the process to pursue personal agendas, can undermine
    the collaborative goals of peer review.

4.  **Keep your feedback constructive and actionable**

    Be helpful and constructive in your feedback. If you see something that
    could be improved, suggest a way to improve it. Don't only just point out
    what's wrong, but also suggest how to fix it, for example by utilising the
    "add suggestion" feature in review comments.

    When there is the possibility to lend out a helping hand, do so. Schedule a
    call or a meeting to discuss the feedback in more detail. This can help to
    clarify the feedback and to make sure that the author understands the
    feedback. It also helps to keep up the pace, and potentially avoid multiple
    review round trips.

5.  **Explain the why**

    Some code might seem wrong to you, but it's likely not obvious to the
    author, or they wouldn't have written it that way. So please don‘t say
    "This is wrong".

    Instead, explain at least what the right way looks like. Or even better,
    explain why they should do things differently. And if you’re the slightest
    bit uncertain, "Maybe I'm missing something, but..." is a helpful sentence.
    Remember, assume competence.

6.  **Find an end**

    If you like things neat, it‘s tempting to go over a code review over and
    over until it’s perfect, dragging it out for longer and taking more time
    than necessary. It‘s soul-deadening for the recipient, though.

    Keep in mind that "LGTM" does not mean "I vouch my immortal soul this will
    never fail", but "looks good to me". If it looks good, move on. That
    doesn’t mean you shouldn‘t be thorough. It’s a judgment call.

    And if there are bigger refactorings to be done or new feature that need to
    be addressed. Then move them to a new issue.

    Especially when there are multiple reviewers, and multiple review rounds,
    it's important to find an end to the review process. Different reviewers
    may have different opinions, and it's important to find a balance between
    the different viewpoints.

7.  **Mention the positives**

    It‘s easy to get into the mindset of "find ALL the flaws", but
    acknowledging the positives both helps maintain civility and brightens the
    recipient’s day.

    No need to be all fake smiles, but if there's a good decision, or if
    somebody takes on a really grungy task, acknowledging that is a nice thing
    to do. And on the converse, a "thank you" to the reviewers is occasionally
    a nice thing, too.

    When you see something cool, when you see a good decision, or when made a
    change that is interesting or innovative, mention it!

8.  **Don't shame people**

    "How could you not see this" is a very unhelpful thing to say. Assume that
    your colleagues do their best, but occasionally make mistakes. That's why
    we have code reviews - to spot those mistakes. While flawless PR's are
    awesome, flawed ones are the norm.

9.  **Don't use extreme or very negative language**

    Please avoid saying things like "no sane person would ever do this" or
    "this approach is terrible", "I can't imagine anyone would want to
    implement it like this".

    Thinly veiled insults or passive aggressive comments are not helpful and
    can be damaging to the relationship. This is useless, petty and nearly
    impossible to act on. While it might intimidate the reviewee into doing
    what you want, it’s not helpful in the long run - they will feel incapable,
    and be less inclined to collaborate with you in the future, and there is
    not much info in there to help them improve.

    "This is a good start, but it could use some work" or "This needs some
    cleanup" are nicer ways of saying it. Discuss the code, not the person.

10. **Don't bikeshed**

    Always ask yourself if this decision really matters in the long run, or if
    you‘re enforcing a subjective preference. It feels good to be right, but
    only one of the two participants can win that game. If it’s not important,
    agree to disagree, and move on. Remember that the goal of the code review
    is to improve the code, not to enforce your personal preferences.

## References

### Books

- [Winters] Software Engineering at Google: Lessons Learned from Programming
  Over Time - Titus Winters, Tom Manshreck, Hyrum Wright
- [Carullo] Implementing Effective Code Reviews: How to Build and Maintain
  Clean Code - Guiliana Carullo
- [Wiegers] Peer Reviews in Software: A Practical Guide - Karl Wiegers

### Websites

- [Deepsource] [deepsource.com - Code review best practices - DeepSource](https://deepsource.com/blog/code-review-best-practices)
- [Wiegers2] [medium.com - The Soft Side of Peer Reviews - Karl Wiegers](https://medium.com/swlh/the-soft-side-of-peer-reviews-ced46d6d63ee)
- [EngPractices] [google.github.io - Google Engineering Practices Documentation | eng-practices](https://google.github.io/eng-practices/)
- [Chromium] [chromium.googlesource.com - Chromium Docs - Respectful Changes](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/docs/cl_respect.md)
- [GoogleTesting] [testing.googleblog.com - Google Testing Blog: Code Health: Respectful Reviews == Useful Reviews](https://testing.googleblog.com/2019/11/code-health-respectful-reviews-useful.html)
- [Thatham] [chiark.greenend.org.uk - Code review antipatterns](https://www.chiark.greenend.org.uk/~sgtatham/quasiblog/code-review-antipatterns/)

[^1]: Adapted from [EngPractices]
[^2]:
    A humorous and insightful take on code review antipatterns can be found
    in [Thatham]
