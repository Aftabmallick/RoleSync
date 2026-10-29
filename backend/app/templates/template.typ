// RoleSync Production ATS Typst Resume Template v2.1
#let resume(
  name: "",
  email: "",
  phone: "",
  location: "",
  linkedin: "",
  github: "",
  summary: "",
  skills: (),
  experience: (),
  projects: (),
  education: (),
  font_size: 9.5pt,
  text_spacing: 110%,
  body
) = {
  set document(title: name + " - Resume", author: name)
  set page(
    paper: "us-letter",
    margin: (x: 0.45in, top: 0.35in, bottom: 0.35in)
  )
  set text(
    font: ("Helvetica", "Arial"),
    size: font_size,
    fill: rgb("#111827"),
    spacing: text_spacing
  )

  // Header Block
  align(center)[
    #text(size: 16pt, weight: "bold", fill: rgb("#030712"))[#name] \
    #v(2pt)
    #text(size: 8.5pt, fill: rgb("#374151"))[
      #email #h(4pt) | #h(4pt)
      #phone #h(4pt) | #h(4pt)
      #location
      #if linkedin != "" [ #h(4pt) | #h(4pt) #link("https://" + linkedin)[#linkedin] ]
      #if github != "" [ #h(4pt) | #h(4pt) #link("https://" + github)[#github] ]
    ]
  ]

  v(2pt)
  line(length: 100%, stroke: 0.5pt + rgb("#D1D5DB"))
  v(2pt)

  // Professional Summary
  if summary != "" [
    #text(weight: "bold", size: 10pt, fill: rgb("#111827"))[PROFESSIONAL SUMMARY] \
    #v(-3pt)
    #line(length: 100%, stroke: 0.4pt + rgb("#E5E7EB"))
    #text(size: font_size * 0.95)[#summary]
    #v(3pt)
  ]

  // Technical Skills Matrix (Categorized)
  if skills.len() > 0 [
    #text(weight: "bold", size: 10pt, fill: rgb("#111827"))[TECHNICAL SKILLS] \
    #v(-3pt)
    #line(length: 100%, stroke: 0.4pt + rgb("#E5E7EB"))
    #for group in skills [
      *#group.category:* #group.items.join(", ") \
    ]
    #v(3pt)
  ]

  // Professional Experience
  if experience.len() > 0 [
    #text(weight: "bold", size: 10pt, fill: rgb("#111827"))[WORK EXPERIENCE] \
    #v(-3pt)
    #line(length: 100%, stroke: 0.4pt + rgb("#E5E7EB"))
    
    #for exp in experience [
      #block(width: 100%)[
        *#exp.role* #h(1fr) #text(size: 8.5pt)[#exp.dates] \
        #text(style: "italic", fill: rgb("#374151"))[#exp.company] #h(1fr) #text(size: 8.5pt, fill: rgb("#4B5563"))[#exp.location] \
        #v(1pt)
        #for bullet in exp.bullets [
          #list(tight: true, marker: [•])[#bullet]
        ]
      ]
      #v(2pt)
    ]
  ]

  // Featured Projects
  if projects.len() > 0 [
    #text(weight: "bold", size: 10pt, fill: rgb("#111827"))[FEATURED PROJECTS] \
    #v(-3pt)
    #line(length: 100%, stroke: 0.4pt + rgb("#E5E7EB"))
    
    #for proj in projects [
      #block(width: 100%)[
        *#proj.name* #if proj.subtitle != "" [ – #text(style: "italic")[#proj.subtitle] ] #if proj.link != "" [ #h(4pt) #text(size: 8pt)[#link(proj.link)[\[GitHub\]]] ] #h(1fr) #text(size: 8.5pt)[#proj.dates] \
        #if proj.technologies != "" [ #text(size: 8pt, fill: rgb("#4B5563"), style: "italic")[#proj.technologies] \ ]
        #v(1pt)
        #for bullet in proj.bullets [
          #list(tight: true, marker: [•])[#bullet]
        ]
      ]
      #v(2pt)
    ]
  ]

  // Education Section
  if education.len() > 0 [
    #text(weight: "bold", size: 10pt, fill: rgb("#111827"))[EDUCATION] \
    #v(-3pt)
    #line(length: 100%, stroke: 0.4pt + rgb("#E5E7EB"))
    #for edu in education [
      *#edu.institution* #h(1fr) #text(size: 8.5pt)[#edu.dates] \
      #edu.degree in #edu.field #h(1fr) #if edu.gpa != "" [ #text(size: 8.5pt)[GPA: #edu.gpa] ] \
    ]
  ]

  body
}
