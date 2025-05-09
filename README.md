# Cloud Inversion RAG Project

This is a working project developed by Chris Butler, starting on 25/01/2025

## Background:
A cloud inversion is a meteorological event characterised by the ability to look down upon cloud formations. The phenomenon typically occurs due to temperature inversions, where higher altitudes are associated with warmer, rather than cooler, temperatures. In short, this warm 'lid' can trap colder air below, including clouds and fog. 

## Example of a Cloud Inversion

![A stunning cloud inversion](https://d3teiib5p3f439.cloudfront.net/news/wp-content/uploads/2015/10/1-3.jpg)


## Goals:
While observing a cloud inversion can occur at relatively low altitudes, Scotland is an excellent place to sight such weather phenomena. This is, in part, due to being the home of 282 Munros—mountains over 3,000 feet in height. Named after the explorer Sir Hugh Munro, climbing these peaks represents a popular challenge for outdoor enthusiasts. While each Munro offers its own beauty, pairing a Munro climb with observing a cloud inversion can create a potentially magical experience for those fortunate enough to witness it.

However, predicting when and where a cloud inversion is likely to occur remains something of a mystery. This software aims to address this by providing:

1) A map of all 282 Munro locations across Scotland.


2) A live RAG (Red, Amber, Green) rating indicating the likelihood of a cloud inversion on a particular date

## Methods:

Currently this software uses Python coding to calculate the RAG cloud inversion rating using the latest weather predictions from [Mountain Forecast](https://www.mountain-forecast.com). It does so based on the guidance provided in by [Our Sporting life](https://oursportinglife.co.uk/cloud-inversions-forecast/) which suggests cloud inversions may be likely if the following criteria are met:

1) The temperature at the top of the summit is greater than that at the bottom of the summit

2) A dew point equal to or higher than the forecast temperature around ground level. The dew point is the temperature at which moisture in the air will form mist

3) Wind speeds of less than 5mph. Higher wind speeds will cause any mist formed to dissipate.

## MoSCoW Analysis: Cloud Inversion Likelihood Application


**1. Must Have (Essential Functionality):**

* **Individual Munro Cloud Inversion Likelihood:**
    * Users must be able to select any individual Munro and retrieve its specific cloud inversion likelihood.
    * This provides granular, mountain-specific data, differentiating it from area-based weather reports.
* **Application-Based Interaction:**
    * The application must be accessible without requiring users to download and execute Python scripts.
* **Data Timestamp:**
    * The date and time of the data retrieval must be clearly displayed to the user.

**2. Should Have (Important Functionality):**

* **Geographical Map Integration:**
    * A map displaying all Munros should be incorporated, enabling users to navigate based on geographical location rather than solely relying on Munro names.
* **Comparative Analysis:**
    * Users should be able to compare cloud inversion likelihood across multiple Munros simultaneously, facilitating informed decision-making for climbing locations.
* **RAG Rating System:**
    * Cloud inversion likelihood should be presented using a Red, Amber, Green (RAG) rating system for quick and intuitive visual assessment.

**3. Could Have (Desirable Functionality):**

* **Future Date Selection:**
    * Users could be given the option to select various future dates and view the corresponding RAG ratings.
* **RAG Rating Component Breakdown:**
    * Users could access a detailed breakdown of the individual components that contribute to the RAG rating for each Munro.

**4. **Would Not Have (Out of Scope):**

* **Non-Munro Site Analysis:**
    * **Users would not have the ability to view cloud inversion likelihood for locations other than Munros.**

## References:

Geographical munro data was sourced from [The Database of British and Irish Hills v18.2](https://www.hills-database.co.uk/downloads.html) 

