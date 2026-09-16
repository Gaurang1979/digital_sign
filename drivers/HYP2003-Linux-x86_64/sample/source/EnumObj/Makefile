OBJ := $(patsubst %.cpp,%.o,$(wildcard *.cpp))
include ../Rule.mak
all: $(OBJ)
	g++ -w -g $^  $(SHLIBS) -o enumobj 
$(OBJ) : %.o : %.cpp
	g++ -w -g -c $< -o $@ 
clean:
	rm -f enumobj  *.o
