import sys
import math

print sys.argv
if len(sys.argv)<5:
	print "Missing parameters!"
	print "Parameters: Blast_File NCBI_Genome_File Average_Read_Length Sequence_Machine"
	print "		1-Blast_File: Blast output file. The format must be in the tablular format, by running blastn with parameter [-outfmt 6]"
	print "		2-NCBI_Genome_File: A file containing the species' names and their length in the NCBI database."
	print "		3-Average_Read_Length: The average read length of the reads in the sample."
	print "		4-Sequence_Machine: 0 for Illumina, 1 for 454 Pyrosequencing. If any other sequencer is used, 0 should be given."
	sys.exit()

print "Constructing the LGF file..."
blastFile=sys.argv[1]
lgfFile=blastFile+".lgf"
ncbiFile=sys.argv[2]
avgLen=int(float(sys.argv[3]))
sequencer=int(sys.argv[4])

ABSOLUTE_ABUNDANCE=0.1
MIN_IDENTITY=97
MIN_ALIGN_LENGTH=97
MIN_MISMATCH=0.0
MIN_GAPS=0.0
MAX_SCORE_DIFF=0
CHUNK_SIZE=2000

if sequencer==0:	##Illumina
	MIN_MISMATCH=0.02
elif sequencer==1:	##Pyro sequencing
	MIN_GAPS=0.03


class Blast_Hit:
	def __init__(self,hit):
		self.readId=hit[0]
		self.species=hit[1]
		self.identity=float(hit[2])
		self.alig_len=float(hit[3])
		self.mismatches=int(hit[4])
		self.gap_opens=int(hit[5])
		self.query_start=int(hit[6])
		self.query_end=int(hit[7])
		self.ref_seq_start=int(hit[8])
		self.ref_seq_end=int(hit[9])
		self.evalue=float(hit[10])
		self.bitScore=float(hit[11])
	def isNewRead(self, oldHit):
		if oldHit==None:
			return 1
		if self.readId!=oldHit.readId:
			return 1
		return 0
	def isGoodScore(self, maxBitScore):
		if maxBitScore-self.bitScore<=MAX_SCORE_DIFF:
			return 1
		return 0
	def updateSpeciesName(self):
		splitGenomeName=self.species.split("_")
		speciesName=splitGenomeName[0]+"_"+splitGenomeName[1]
		if "sp." in splitGenomeName[1]:
			speciesName += "_"+splitGenomeName[2]
		self.species=speciesName
	def printHit(self):
		print(self.readId+"\t"+self.species+str(self.identity)+str(self.alig_len)+str(self.mismatches)+str(self.gap_opens)+str(self.query_start)+str(self.query_end)+str(self.ref_seq_start)+str(self.ref_seq_end)+str(self.evalue)+str(self.bitScore))

class Genome:
	def __init__(self, genomeId, genomeName, genomeLength, chunkSize):
		self.genomeId=genomeId
		self.genomeName=genomeName
		self.genomeLength=genomeLength
		self.numOfReads=0
		self.chunkSize=chunkSize
		self.absAbundance=0.0
		self.relAbundance=0.0
		self.numOfChunks=self.getChunkNum(self.genomeLength)+1
		self.chunks=None
		self.reads=None

	def getChunkNum(self, start):
		if(start%self.chunkSize==0):
			return (start/self.chunkSize)-1;
		return start/self.chunkSize

	def createChunks(self):
		self.chunks=list()
		for i in range(0,self.numOfChunks):
			self.chunks.append(dict())

	def addHit(self, blastHit):
		if blastHit.ref_seq_start >self.genomeLength:
			return
		if self.chunks==None:
			self.createChunks()
			self.reads=set()
		chunkNum=self.getChunkNum(blastHit.ref_seq_start)		
		chunkReads=self.chunks[chunkNum]
		if blastHit.readId not in chunkReads:
			chunkReads[blastHit.readId]=blastHit.bitScore
		elif chunkReads[blastHit.readId]< blastHit.bitScore:
			chunkReads[blastHit.readId]=blastHit.bitScore
		if blastHit.readId not in self.reads:
			self.reads.add(blastHit.readId)

	def setAbsAbundance(self):
		if self.chunks!=None:
			self.absAbundance=float(len(self.reads)*avgLen)/float(self.genomeLength)	

	def isLowAbundance(self):
		if self.absAbundance<ABSOLUTE_ABUNDANCE:
			return 1
		return 0

def createNCBIDatabase(ncbi):
	ncbiSpecies=dict()
	speciesId=0
	with open(ncbi) as ncbiFile:
		for line in ncbiFile:
			splitLine=line.strip().split("\t")
			species=splitLine[0]
			length=int(splitLine[1])
			g=Genome(speciesId, species, length, CHUNK_SIZE)
			ncbiSpecies[species]=g
			speciesId+=1		
	ncbiFile.close()
	return ncbiSpecies


def addBlastHits(blastHitList, maxBitScore, refGenomes):
	for blastHit in blastHitList:
		if blastHit.readId == "SRR1804065.190.2":
			blastHit.printHit()
		if blastHit.isGoodScore(maxBitScore)==0:
			if blastHit.readId == "SRR1804065.190.2":
				print "Not good Score!"
			continue
		if blastHit.alig_len<MIN_ALIGN_LENGTH:
			if blastHit.readId == "SRR1804065.190.2":
				print "Short alignment length!"
			continue
		if blastHit.identity< MIN_IDENTITY:
			if blastHit.readId == "SRR1804065.190.2":
				print "Low Identity Score!"
			continue
		blastHit.updateSpeciesName()
		refGenomes[blastHit.species].addHit(blastHit)

def createLGF(blastFile, ncbiFile, lgfFile):
	refGenomes=createNCBIDatabase(ncbiFile)
	previousBlastHit=None
	maxBitScore=0
	blastHitList=list()
	with open(blastFile) as f:
		for line in f:
			splitLine=line.strip().split("\t")
			blastHit=Blast_Hit(splitLine)
			if blastHit.isNewRead(previousBlastHit)==1: 
				addBlastHits(blastHitList, maxBitScore, refGenomes)
				maxBitScore=0
				blastHitList=[]
				previousBlastHit=blastHit
			blastHitList.append(blastHit)	
			if blastHit.bitScore > maxBitScore:
				maxBitScore=blastHit.bitScore
	addBlastHits(blastHitList, maxBitScore, refGenomes)
	f.close()
	writeLGF(refGenomes, lgfFile)

def writeLGF(speciesDict, lgfFile):
	readSet=set()
	lgf=open(lgfFile, "w")
	lgf.write("@nodes\nlabel\tgenome\t\n")
	#totalAbundance=0.0
	maxScore=0
	minScore=1000000
	nOfGenomes=0
	for species in speciesDict:
		genome=speciesDict[species]
		genome.setAbsAbundance()
		if genome.isLowAbundance()!=1:
			nOfGenomes+=1
			genomeId=str(genome.genomeId)
			for i in range(0,genome.numOfChunks):
				chunkId=str(i)
				lgf.write(genomeId+"_"+chunkId+"\t"+genomeId+"\n")
	for species in speciesDict:
		genome=speciesDict[species]
		genome.setAbsAbundance()
		if genome.isLowAbundance()!=1:
			#totalAbundance+=genome.absAbundance
			for reads in genome.chunks:				
				for read, weight in reads.iteritems():
					if weight<minScore:
						minScore=weight
					if weight >maxScore:
						maxScore=weight
					if read not in readSet:
						readSet.add(read)
						lgf.write(read+"\t-1\n")
	lgf.write("@arcs\n\t\tlabel\tcost\n")
	counter=0	
	print "Max_Score: "+str(maxScore)+"\tMin_Score: "+str(minScore)
	for species in speciesDict:
		genome=speciesDict[species]
		if genome.isLowAbundance()!=1:
			genomeId=str(genome.genomeId)			
			for idx, reads in enumerate(genome.chunks):
				chunkId=str(idx)
				for read, weight in reads.iteritems():
					cost=int(abs(weight-maxScore)+100)					
					lgf.write(read+"\t"+genomeId+"_"+chunkId+"\t"+str(counter)+"\t"+str(cost)+"\n")
					counter+=1
	
	maxScore=int(abs(minScore-maxScore)+100)
	lgf.write("@attributes\n")		
	lgf.write("number_of_genomes\t"+str(nOfGenomes)+"\n")
	lgf.write("number_of_mapping_reads\t"+str(len(readSet))+"\n")
	lgf.write("avg_read_length\t"+str(avgLen)+"\n")
	lgf.write("max_cost\t"+str(maxScore)+"\n")
	lgf.write("min_cost\t"+str(100)+"\n")
	lgf.close()	

createLGF(blastFile, ncbiFile, lgfFile)
